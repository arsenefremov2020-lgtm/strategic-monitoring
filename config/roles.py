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
# Тимчасове вимкнення особистих кабінетів
# -----------------------------

# False = рольові обмеження та особисті кабінети тимчасово вимкнені:
# усі вкладки показуються для всіх користувачів,
# а guard-перевірки сторінок не блокують доступ.
# True = повернення до логіки особистих кабінетів і доступів за ролями.
ENABLE_PERSONAL_CABINETS = False


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
    Якщо особисті кабінети вимкнені — повертає всі вкладки.
    """

    if not ENABLE_PERSONAL_CABINETS:
        return ALL_PAGES.copy()

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
    Якщо особисті кабінети вимкнені — не блокує жодну сторінку.
    """

    if not ENABLE_PERSONAL_CABINETS:
        return True

    if not page_name:
        return False

    allowed_pages = get_pages_for_role(role)
    return page_name in allowed_pages


def is_admin_role(role: str | None) -> bool:
    """
    Перевіряє, чи є користувач адміністратором або супер-адміном.
    Якщо особисті кабінети вимкнені — адміністративні перевірки не блокують інтерфейс.
    """

    if not ENABLE_PERSONAL_CABINETS:
        return True

    role = normalize_role(role)
    return role in [ROLE_ADMIN, ROLE_SUPER_ADMIN]


def is_super_admin(role: str | None) -> bool:
    """
    Перевіряє, чи є користувач супер-адміном.
    Якщо особисті кабінети вимкнені — повертає True для сумісності з адмін-сторінками.
    """

    if not ENABLE_PERSONAL_CABINETS:
        return True

    role = normalize_role(role)
    return role == ROLE_SUPER_ADMIN


def is_ssp_role(role: str | None) -> bool:
    """
    Перевіряє, чи є користувач представником ССП або керівником ССП.
    Якщо особисті кабінети вимкнені — не вмикає режим персонального ССП.
    """

    if not ENABLE_PERSONAL_CABINETS:
        return False

    role = normalize_role(role)
    return role in [ROLE_SSP, ROLE_SSP_HEAD]
