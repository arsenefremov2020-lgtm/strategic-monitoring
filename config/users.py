# config/users.py

"""
Список користувачів системи моніторингу стратегічного плану.

Цей файл відповідає тільки за:
1. перелік користувачів;
2. їхні ролі;
3. прив'язку до ССП;
4. службові функції для пошуку користувача за email.

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


# -----------------------------
# Список користувачів
# -----------------------------

USERS = {
    "vperun80@gmail.com": {
        "email": "vperun80@gmail.com",
        "full_name": "Вікторія Перун",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Супер-адмін",
        "ssp": None,
        "is_active": True,
        "is_owner": False,
    },

    "arsen.efremov.2020@gmail.com": {
        "email": "arsen.efremov.2020@gmail.com",
        "full_name": "Арсен Єфремов",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Власник",
        "ssp": None,
        "is_active": True,
        "is_owner": True,
    },

    "chemodanovayuliya123@gmail.com": {
        "email": "chemodanovayuliya123@gmail.com",
        "full_name": "Юлія Чемоданова",
        "role": ROLE_ADMIN,
        "role_label": "Адміністратор",
        "ssp": None,
        "is_active": True,
        "is_owner": False,
    },

    "kanevska150881@gmail.com": {
        "email": "kanevska150881@gmail.com",
        "full_name": "Каневська",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Супер-адмін",
        "ssp": None,
        "is_active": True,
        "is_owner": False,
    },

    "t.kovalchuk1979@gmail.com": {
        "email": "t.kovalchuk1979@gmail.com",
        "full_name": "Тетяна Ковальчук",
        "role": ROLE_ADMIN,
        "role_label": "Адміністратор",
        "ssp": None,
        "is_active": True,
        "is_owner": False,
    },

    "arsen.yefremov.25@kse.org.ua": {
        "email": "arsen.yefremov.25@kse.org.ua",
        "full_name": "Тестовий користувач ССП",
        "role": ROLE_SSP,
        "role_label": "Кабінет ССП",
        "ssp": "Тестовий ССП",
        "is_active": True,
        "is_owner": False,
    },

    "inna.mogilat@gmail.com": {
        "email": "inna.mogilat@gmail.com",
        "full_name": "Інна Могилат",
        "role": ROLE_SUPER_ADMIN,
        "role_label": "Супер-адмін",
        "ssp": None,
        "is_active": True,
        "is_owner": False,
    },

    "test.ssp.head@example.com": {
        "email": "test.ssp.head@example.com",
        "full_name": "Тестовий керівник ССП",
        "role": ROLE_SSP_HEAD,
        "role_label": "Керівник ССП",
        "ssp": "Тестовий ССП",
        "is_active": True,
        "is_owner": False,
    },
}


# -----------------------------
# Гостьовий користувач
# -----------------------------

GUEST_USER = {
    "email": None,
    "full_name": "Користувач без реєстрації",
    "role": ROLE_GUEST,
    "role_label": "Користувач без реєстрації",
    "ssp": None,
    "is_active": True,
    "is_owner": False,
}


# -----------------------------
# Службові функції
# -----------------------------

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

    user_data = user.copy()

    user_data["role"] = normalize_role(user_data.get("role"))
    user_data["role_label"] = user_data.get("role_label") or get_role_label(user_data.get("role"))

    return user_data


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
    Повертає ССП користувача.
    Для адмінів, супер-адмінів і гостей повертає None.
    """

    user = get_user_by_email(email)
    return user.get("ssp")


def get_all_users() -> dict:
    """
    Повертає копію всіх користувачів.
    """

    return USERS.copy()


def get_active_users() -> dict:
    """
    Повертає тільки активних користувачів.
    """

    return {
        email: user
        for email, user in USERS.items()
        if user.get("is_active", False)
    }


def get_users_by_role(role: str) -> dict:
    """
    Повертає користувачів із конкретною роллю.
    """

    role = normalize_role(role)

    return {
        email: user
        for email, user in USERS.items()
        if normalize_role(user.get("role")) == role and user.get("is_active", False)
    }


def get_users_by_ssp(ssp: str | None) -> dict:
    """
    Повертає користувачів, прив'язаних до конкретного ССП.
    """

    if not ssp:
        return {}

    ssp = str(ssp).strip()

    return {
        email: user
        for email, user in USERS.items()
        if user.get("ssp") == ssp and user.get("is_active", False)
    }
