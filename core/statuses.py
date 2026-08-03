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

from core.approval_schemes import ALL_RETURNED_STATUSES, ALL_WAITING_STATUSES
from core.period_locks import all_periods_locked, exclude_locked_periods, is_period_locked
from core.timeutils import now_kyiv

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
    ST_DONE:     {"bg": "#E4F5EC", "fg": "#0C713A", "border": "#1E9E57"},
    ST_PARTIAL:  {"bg": "#FDF3D8", "fg": "#8A6400", "border": "#F4B400"},
    ST_NOTDONE:  {"bg": "#FBE5E5", "fg": "#DC4A4A", "border": "#DC4A4A"},
    ST_NOTYET:   {"bg": "#FFFFFF", "fg": "#61708A", "border": "#DCE4F0"},
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
    "На розгляді":             {"bg": "#E3EDFF", "fg": "#032A63", "border": "#4D8DFF"},
    "На доопрацюванні":        {"bg": "#FDF3D8", "fg": "#8A6400", "border": "#F4B400"},
    "Погоджено":               {"bg": "#E4F5EC", "fg": "#0C713A", "border": "#1E9E57"},
    "Не настав час":           {"bg": "#FFFFFF", "fg": "#61708A", "border": "#DCE4F0"},
    "Не враховано":            {"bg": "#FBE5E5", "fg": "#DC4A4A", "border": "#DC4A4A"},
    "Закрито адміністратором": {"bg": "#ede9fe", "fg": "#5b21b6", "border": "#c4b5fd"},
}


def legend_badge(
    state: object,
    extra_style: str = "",
    *,
    display_value: object | None = None,
) -> str:
    """Готовий HTML-бейдж за єдиною легендою системи.

    За замовчуванням показує назву стану. ``display_value`` дозволяє
    використати той самий колірний механізм для фактичного значення
    (наприклад, у квартальній клітинці головної таблиці).
    """
    from html import escape as _escape

    s = clean(state)
    c = LEGEND_COLORS.get(s, LEGEND_COLORS["Не враховано"])
    label = s if s in LEGEND_COLORS else "Не враховано"
    text_color = c["fg"]
    text_weight = 800
    if display_value is None:
        if label == "Закрито адміністратором":
            label = "🔒 Закрито адміністратором"
    else:
        label = clean(display_value) or "—"
        text_color = "#132238"
        text_weight = 900
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'font-size:11px;font-weight:{text_weight};background:{c["bg"]};'
        f'color:{text_color};border:1px solid {c["border"]};'
        f'{extra_style}">{_escape(label)}</span>'
    )


def legend_badge_image_uri(
    state: object,
    *,
    display_value: object | None = None,
) -> str:
    """SVG data-URI бейджа для ``st.data_editor`` / ``ImageColumn``.

    Використовує ту саму ``LEGEND_COLORS`` і семантику, що й ``legend_badge``.
    Це дозволяє показати овальну пігулку всередині canvas-таблиці Streamlit,
    де HTML із ``legend_badge`` не рендериться.
    """
    from html import escape as _escape
    from urllib.parse import quote as _quote

    s = clean(state)
    c = LEGEND_COLORS.get(s, LEGEND_COLORS["Не враховано"])
    label = clean(display_value) if display_value is not None else s
    label = label or "—"
    width = max(52, min(240, 24 + len(label) * 8))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" '
        f'viewBox="0 0 {width} 28">'
        f'<rect x="1" y="1" width="{width - 2}" height="26" rx="13" '
        f'fill="{c["bg"]}" stroke="{c["border"]}" stroke-width="1"/>'
        f'<text x="{width / 2}" y="18" text-anchor="middle" '
        f'font-family="Arial, sans-serif" font-size="11" font-weight="800" '
        f'fill="{c["fg"]}">{_escape(label)}</text></svg>'
    )
    return "data:image/svg+xml;charset=UTF-8," + _quote(svg, safe="")


# ── Єдина логіка візуального статусу моніторингового запису ──

def business_days_between(start, end) -> int:
    """Кількість робочих днів; поточний момент передається у київському часі."""
    start_ts = pd.to_datetime(start, errors="coerce")
    end_ts = pd.to_datetime(end, errors="coerce")
    if pd.isna(start_ts) or pd.isna(end_ts):
        return 0
    # Для порівняння календарних дат приводимо aware timestamps до Києва.
    try:
        if getattr(start_ts, "tzinfo", None) is not None:
            start_ts = start_ts.tz_convert("Europe/Kyiv")
    except Exception:
        pass
    try:
        if getattr(end_ts, "tzinfo", None) is not None:
            end_ts = end_ts.tz_convert("Europe/Kyiv")
    except Exception:
        pass
    start_date = start_ts.date()
    end_date = end_ts.date()
    if end_date <= start_date:
        return 0
    return len(pd.bdate_range(start=start_date, end=end_date, inclusive="right"))


def is_overdue_review_record(row) -> bool:
    approval = clean(row.get("approval_status", ""))
    if approval not in ALL_WAITING_STATUSES:
        return False
    submitted = pd.to_datetime(row.get("submitted_at", None), errors="coerce", utc=True)
    if pd.isna(submitted):
        return False
    return business_days_between(submitted, pd.Timestamp(now_kyiv())) > 5


def get_record_visual_status(row) -> str:
    """Єдина точка визначення візуального статусу запису; period_locks має найвищий пріоритет."""
    if is_period_locked(row.get("year", ""), row.get("quarter", "")):
        return ST_NOTYET

    approval = clean(row.get("approval_status", ""))
    execution_status = clean(row.get("status", ""))

    if approval == "Погоджено":
        return "Погоджено"
    if approval in ALL_RETURNED_STATUSES:
        return "На доопрацюванні"
    if approval in ALL_WAITING_STATUSES:
        return "На розгляді"
    if execution_status == ST_NOTYET:
        return ST_NOTYET
    return "Не враховано"


def get_measure_records(monitoring_df: pd.DataFrame, code, selected_years, selected_quarters) -> pd.DataFrame:
    if monitoring_df is None or monitoring_df.empty:
        return pd.DataFrame()
    years_as_str = [str(y).strip() for y in (selected_years or [])]
    quarters_as_str = [str(q).replace(" квартал", "").strip() for q in (selected_quarters or [])]
    data = monitoring_df.copy()
    data = data[data["strat_code"].astype(str).str.strip() == str(code).strip()]
    if years_as_str:
        data = data[data["year"].astype(str).str.strip().isin(years_as_str)]
    if quarters_as_str:
        data = data[data["quarter"].astype(str).str.strip().isin(quarters_as_str)]
    return data.copy()


def get_measure_status(monitoring_df: pd.DataFrame, code, selected_years, selected_quarters) -> str:
    """Агрегований статус заходу; period_locks не спотворюють змішані вибірки."""
    if all_periods_locked(selected_years or [], selected_quarters or []):
        return ST_NOTYET

    records = get_measure_records(monitoring_df, code, selected_years, selected_quarters)
    if records.empty:
        return "Не враховано"

    # Якщо вибрано і заблоковані, і робочі квартали, записи заблокованих
    # кварталів повністю ігноруємо. Інакше наявність даних лише в Q1/Q2 2026
    # могла помилково дати «Не настав час» для вибірки, що також містить Q3/Q4.
    effective_records = exclude_locked_periods(records)
    if effective_records.empty:
        return "Не враховано"

    statuses = [
        get_record_visual_status(row)
        for _, row in effective_records.iterrows()
    ]
    effective = [status for status in statuses if status != ST_NOTYET]
    if not effective and ST_NOTYET in statuses:
        return ST_NOTYET
    if "Погоджено" in effective:
        return "Погоджено"
    if "На розгляді" in effective:
        return "На розгляді"
    if "На доопрацюванні" in effective:
        return "На доопрацюванні"
    return "Не враховано"


def visual_status_class(status: object) -> str:
    value = clean(status)
    if value == "Погоджено":
        return "status-approved"
    if value == "На розгляді":
        return "status-review"
    if value == "На доопрацюванні":
        return "status-returned"
    if value == ST_NOTYET:
        return "status-notyet"
    return "status-empty"
