# core/statuses.py

"""
ЄДИНА шкала статусів виконання (правка К5 / П1 / П5).

Стандарт — модель «Оцінка МіО» (Excel): для заходів існує рівно
5 статусів (випадний список $AR$1:$AR$5 аркуша «М_заходи»):

    Виконано · Частково виконано · Не виконано ·
    Не настав час · Втратило актуальність

Шкала балів — точно за довідником $AD/$AE аркуша «РВ (Заходи)»:
    Виконано → 100 · Частково виконано → 75 · Не виконано → 0 ·
    Не настав час / Втратило актуальність → виключаються з розрахунку (None).

Історичні статуси зі старих тестових подань («Виконується»,
«Прострочено», «Потребує уваги», «Не розпочато», «Не подано»)
зводяться до «Не виконано» — в моделі таких станів немає.

ВАЖЛИВО (виправлення П1): бали визначаються ТІЛЬКИ точною відповідністю
канонічному статусу, а не входженням підрядка — раніше «Не виконано»
через підрядок «виконано» помилково отримувало 100 балів.
"""

from __future__ import annotations

import pandas as pd

# ── Канонічні статуси моделі (Excel $AR$1:$AR$5) ──
ST_DONE = "Виконано"
ST_PARTIAL = "Частково виконано"
ST_NOTDONE = "Не виконано"
ST_NOTYET = "Не настав час"
ST_OBSOLETE = "Втратило актуальність"

MODEL_STATUSES = [ST_DONE, ST_PARTIAL, ST_NOTDONE, ST_NOTYET, ST_OBSOLETE]

# Статуси, доступні у формах подання (той самий набір, у порядку списку Excel)
SUBMISSION_STATUS_OPTIONS = list(MODEL_STATUSES)

# Бали за статус — довідник $AD/$AE аркуша «РВ (Заходи)»
STATUS_SCORES = {
    ST_DONE: 100,
    ST_PARTIAL: 75,
    ST_NOTDONE: 0,
    ST_NOTYET: None,      # «х» — виключається з розрахунку
    ST_OBSOLETE: None,    # «в/а» — виключається з розрахунку
}

# Кольори бейджів статусів (поточна палітра системи)
STATUS_COLORS = {
    ST_DONE:     {"bg": "#dcfce7", "fg": "#166534", "border": "#86efac"},
    ST_PARTIAL:  {"bg": "#fef9c3", "fg": "#854d0e", "border": "#fde047"},
    ST_NOTDONE:  {"bg": "#fee2e2", "fg": "#991b1b", "border": "#fca5a5"},
    ST_NOTYET:   {"bg": "#e0e7ef", "fg": "#334155", "border": "#cbd5e1"},
    ST_OBSOLETE: {"bg": "#ede9fe", "fg": "#5b21b6", "border": "#c4b5fd"},
}


def clean(value: object) -> str:
    """Return a safe stripped string."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def status_display(status: object) -> str:
    """Зводить будь-який статус (вкл. історичні) до 5 канонічних моделі."""
    return normalize_to_model_status(status) or ST_NOTDONE


def normalize_to_model_status(value: object) -> str:
    """
    Зводить статус із моніторингу до 5 категорій моделі «М_заходи».
    Порожнє / нерозпізнане → "" (немає даних).
    """
    t = clean(value).lower().replace("’", "'")
    if not t or t in ["nan", "none", "-", "—", "н.д.", "нд"]:
        return ""
    if "втрат" in t and "актуальн" in t:
        return ST_OBSOLETE
    if "не настав" in t or "не настало" in t or "не настане" in t or "термін не настав" in t:
        return ST_NOTYET
    if "частков" in t:  # «виконано частково» / «частково виконано»
        return ST_PARTIAL
    # Історичні стани «в процесі / провалено» → «Не виконано»
    if ("виконується" in t or "не викон" in t or "не розпоч" in t
            or "простроч" in t or "потребує уваги" in t or "не подано" in t
            or t == "ні"):
        return ST_NOTDONE
    if t == ST_DONE.lower() or t == "так" or t == "виконано":
        return ST_DONE
    # вже канонічний?
    canonical = {s.lower(): s for s in MODEL_STATUSES}
    return canonical.get(t, "")


def is_excluded_status(status: object) -> bool:
    """True для статусів, що виключаються з формул оцінки («х» / «в/а»)."""
    return status_display(status) in [ST_NOTYET, ST_OBSOLETE]


def status_score(status: object):
    """
    Бал за статус за єдиною шкалою моделі (Excel «РВ (Заходи)»).
    ТОЧНА відповідність канонічному статусу після нормалізації (П1).
    Повертає 100 / 75 / 0 або None (виключено з розрахунку).
    """
    canonical = normalize_to_model_status(status)
    if not canonical:
        return 0
    return STATUS_SCORES[canonical]


def status_badge(status: object, extra_style: str = "") -> str:
    """Готовий HTML-бейдж статусу в єдиному стилі."""
    canonical = status_display(status)
    c = STATUS_COLORS.get(canonical, STATUS_COLORS[ST_NOTDONE])
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'font-size:11px;font-weight:800;background:{c["bg"]};color:{c["fg"]};'
        f'border:1px solid {c["border"]};{extra_style}">{canonical}</span>'
    )


# ── Єдина легенда СТАНІВ ПОДАННЯ (звітних даних) ──
# Це НЕ статуси виконання (їх 5 вище), а стани клітинок звітності з легенди
# головної сторінки: 🟦 На розгляді · 🟨 На доопрацюванні · 🟩 Погоджено ·
# ⬜ Не настав час · 🟥 Не враховано · 🟪 Закрито адміністратором.
# Використовується всіма сторінками, щоб кольори збігалися ВСЮДИ.

LEGEND_STATES = [
    "На розгляді", "На доопрацюванні", "Погоджено",
    "Не настав час", "Не враховано", "Закрито адміністратором",
]

LEGEND_COLORS = {
    "На розгляді":             {"bg": "#dbeafe", "fg": "#1e40af", "border": "#93c5fd"},
    "На доопрацюванні":        {"bg": "#fef9c3", "fg": "#854d0e", "border": "#fde047"},
    "Погоджено":               {"bg": "#dcfce7", "fg": "#166534", "border": "#86efac"},
    "Не настав час":           {"bg": "#e0e7ef", "fg": "#334155", "border": "#cbd5e1"},
    "Не враховано":            {"bg": "#fee2e2", "fg": "#991b1b", "border": "#fca5a5"},
    "Закрито адміністратором": {"bg": "#ede9fe", "fg": "#5b21b6", "border": "#c4b5fd"},
}


def legend_badge(state: object, extra_style: str = "") -> str:
    """Готовий HTML-бейдж стану подання за єдиною легендою системи."""
    s = clean(state)
    c = LEGEND_COLORS.get(s, LEGEND_COLORS["Не враховано"])
    label = s if s in LEGEND_COLORS else "Не враховано"
    if label == "Закрито адміністратором":
        label = "🔒 Закрито адміністратором"
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'font-size:11px;font-weight:800;background:{c["bg"]};color:{c["fg"]};'
        f'border:1px solid {c["border"]};{extra_style}">{label}</span>'
    )
