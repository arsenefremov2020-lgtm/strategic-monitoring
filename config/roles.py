# config/roles.py

"""
Налаштування ролей користувачів та доступних вкладок.

Цей файл відповідає тільки за:
1. назви ролей;
2. перелік вкладок, доступних для кожної ролі;
3. службові функції для перевірки доступу.

Тут не має бути логіки Streamlit, Supabase, Excel або розрахунків.
"""


# -----------------------------
# Назви ролей
# -----------------------------

ROLE_SSP = "ssp"
ROLE_SSP_HEAD = "ssp_head"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
ROLE_GUEST = "guest"


# -----------------------------
# Людські назви ролей
# -----------------------------

ROLE_LABELS = {
    ROLE_SSP: "Кабінет ССП",
    ROLE_SSP_HEAD: "Керівник ССП",
    ROLE_ADMIN: "Адміністратор",
    ROLE_SUPER_ADMIN: "Супер-адмін",
    ROLE_GUEST: "Користувач без реєстрації",
}


# -----------------------------
# Доступні вкладки для кожної ролі
# -----------------------------

ROLE_PAGES = {
    ROLE_SSP: [
        "app",
        "Моніторинг виконання",
        "Dashboard",
        "Картка заходу",
        "Мої заявки",
    ],

    ROLE_SSP_HEAD: [
        "app",
        "Dashboard",
        "Мій кабінет",
        "Картка заходу",
    ],

    ROLE_ADMIN: [
        "app",
        "Dashboard",
        "Адміністрування",
        "Картка заходу",
    ],

    ROLE_SUPER_ADMIN: [
        "app",
        "Dashboard",
        "Адміністрування",
        "Картка заходу",
        "Оцінка МіО",
        "Журнал дій",
        "Аналітика",
    ],

    ROLE_GUEST: [
        "app",
        "Dashboard",
        "Картка заходу",
    ],
}


# -----------------------------
# Усі можливі вкладки системи
# -----------------------------

ALL_PAGES = [
    "app",
    "Моніторинг виконання",
    "Dashboard",
    "Картка заходу",
    "Мої заявки",
    "Мій кабінет",
    "Адміністрування",
    "Оцінка МіО",
    "Журнал дій",
    "Аналітика",
]


# -----------------------------
# Сторінка за замовчуванням
# -----------------------------

DEFAULT_PAGE_BY_ROLE = {
    ROLE_SSP: "app",
    ROLE_SSP_HEAD: "app",
    ROLE_ADMIN: "app",
    ROLE_SUPER_ADMIN: "app",
    ROLE_GUEST: "app",
}


# -----------------------------
# Службові функції
# -----------------------------

def normalize_role(role: str | None) -> str:
    """
    Повертає валідну роль.
    Якщо роль порожня або невідома — повертає guest.
    """

    if not role:
        return ROLE_GUEST

    role = str(role).strip()

    if role in ROLE_PAGES:
        return role

    return ROLE_GUEST


def get_role_label(role: str | None) -> str:
    """
    Повертає людську назву ролі.
    """

    role = normalize_role(role)
    return ROLE_LABELS.get(role, ROLE_LABELS[ROLE_GUEST])


def get_pages_for_role(role: str | None) -> list[str]:
    """
    Повертає список вкладок, доступних для конкретної ролі.
    """

    role = normalize_role(role)
    return ROLE_PAGES.get(role, ROLE_PAGES[ROLE_GUEST])


def get_default_page_for_role(role: str | None) -> str:
    """
    Повертає стартову сторінку для ролі.
    """

    role = normalize_role(role)
    return DEFAULT_PAGE_BY_ROLE.get(role, "app")


def can_access_page(role: str | None, page_name: str) -> bool:
    """
    Перевіряє, чи має роль доступ до конкретної вкладки.
    """

    if not page_name:
        return False

    allowed_pages = get_pages_for_role(role)
    return page_name in allowed_pages


def is_admin_role(role: str | None) -> bool:
    """
    Перевіряє, чи є користувач адміністратором або супер-адміном.
    """

    role = normalize_role(role)
    return role in [ROLE_ADMIN, ROLE_SUPER_ADMIN]


def is_super_admin(role: str | None) -> bool:
    """
    Перевіряє, чи є користувач супер-адміном.
    """

    role = normalize_role(role)
    return role == ROLE_SUPER_ADMIN


def is_ssp_role(role: str | None) -> bool:
    """
    Перевіряє, чи є користувач представником ССП або керівником ССП.
    """

    role = normalize_role(role)
    return role in [ROLE_SSP, ROLE_SSP_HEAD]
