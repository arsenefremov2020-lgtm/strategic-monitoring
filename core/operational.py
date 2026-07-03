# core/operational.py

"""
Два паралельні процеси оцінки виконання (правка №6).

ПІДТВЕРДЖЕНІ дані — офіційний процес: у розрахунок ідуть лише заявки зі
статусом «Погоджено» (як було завжди).

ОПЕРАТИВНА ОЦІНКА — паралельний процес: для заходів, за якими ще НЕМАЄ
підтвердженого запису за період, використовується подання, яке
координатор уже пропустив далі по схемі погодження (тобто перебуває на
етапі ПІСЛЯ ланки координатора). Якщо подане значення відповідає річному
цільовому орієнтиру або краще — захід автоматично вважається ВИКОНАНИМ
(⚡ авто-зараховано), не чекаючи фінального підпису.

Правила (за специфікацією замовника):
- квартальні значення НЕ накопичуються: порівнюється саме подане значення
  «станом на квартал» із річним цільовим орієнтиром;
- «Повернуто на доопрацювання» та «Очікує погодження» (ще у координатора
  або до нього) — НЕ враховуються в оперативній оцінці;
- пріоритет індивідуально по кожному заходу: є підтверджений запис —
  береться він; немає — береться оперативний;
- якщо після підтвердження дані змінилися — система просто перерахує
  (оперативний запис заміниться підтвердженим).
"""

from __future__ import annotations

import re

import pandas as pd

from core.approval_schemes import parse_chain, parse_stage

CONFIRMED_STATUS = "Погоджено"

# Успадкований статус «після координатора»
LEGACY_PAST_ADMIN_STATUSES = {"Направлено на підпис"}

# Статуси, які точно НЕ пройшли координатора / вибули з процесу
NOT_PAST_ADMIN_STATUSES = {"Очікує погодження", "Повернуто на доопрацювання", ""}

AUTO_DONE_STATUS = "Виконано"

MODE_CONFIRMED = "✅ Підтверджені дані"
MODE_OPERATIONAL = "⚡ Оперативна оцінка"
MODE_OPTIONS = [MODE_CONFIRMED, MODE_OPERATIONAL]

MODE_HELP = (
    "«Підтверджені дані» — лише заявки, що пройшли ВСІ етапи схеми погодження "
    "(офіційний процес). «Оперативна оцінка» — додатково враховує подання, які "
    "координатор уже пропустив далі по схемі: якщо значення відповідає річному "
    "цільовому орієнтиру або краще, захід автоматично зараховується як виконаний "
    "(позначка ⚡), не чекаючи фінального підпису. Для кожного заходу пріоритет "
    "мають підтверджені дані."
)


# ------------------------------------------------------------
# Розбір значень і порівняння з річним орієнтиром
# ------------------------------------------------------------

_YES_WORDS = {"так", "виконано", "прийнято", "ухвалено", "yes", "done", "+"}


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "null") else text


def parse_number(value) -> float | None:
    """Витягує число з тексту: '85,5 %' → 85.5, '1 250' → 1250."""
    text = _clean(value)
    if not text:
        return None
    normalized = text.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def target_met(fact_value, target_value) -> bool:
    """
    True, якщо подане значення відповідає річному орієнтиру або краще.

    - Числа: факт ≥ план (стандартна логіка «більше — краще», як у
      співвідношенні Факт/План аркуша М_заходи).
    - «Так/Ні»-індикатори: факт містить стверджувальне слово, якщо план
      теж «так» або план нечисловий.
    - Якщо орієнтир порожній — авто-зарахування неможливе (повертає False).
    """
    target_text = _clean(target_value).lower()
    fact_text = _clean(fact_value).lower()

    if not target_text or not fact_text:
        return False

    fact_num = parse_number(fact_value)
    target_num = parse_number(target_value)

    if fact_num is not None and target_num is not None:
        return fact_num >= target_num

    # Нечислові («так», «прийнято НПА» тощо)
    return any(word in fact_text for word in _YES_WORDS)


# ------------------------------------------------------------
# «Після координатора?»
# ------------------------------------------------------------

def is_past_admin(record) -> bool:
    """
    True, якщо заявка вже пройшла ланку координатора і перебуває на
    наступному етапі схеми погодження (але ще не «Погоджено»).
    """
    status = _clean(record.get("approval_status") if hasattr(record, "get") else "")

    if status == CONFIRMED_STATUS:
        return False  # це вже підтверджений запис, не «оперативний»
    if status in NOT_PAST_ADMIN_STATUSES:
        return False

    chain = parse_chain(record.get("approval_chain")) if hasattr(record, "get") else []
    if chain:
        stage_idx = parse_stage(record.get("chain_stage"))
        admin_positions = [i for i, stg in enumerate(chain) if stg.get("role") == "admin"]
        if not admin_positions:
            return False
        return stage_idx > admin_positions[0]

    # Успадковані заявки без ланцюга
    return status in LEGACY_PAST_ADMIN_STATUSES


# ------------------------------------------------------------
# Оперативний індекс подань
# ------------------------------------------------------------

def _quarter_key(value) -> str:
    text = _clean(value).upper().replace("КВАРТАЛ", "").replace("КВ.", "").strip()
    mapping = {"1": "I", "2": "II", "3": "III", "4": "IV",
               "I": "I", "ІІ": "II", "II": "II", "III": "III", "IV": "IV"}
    if text in mapping:
        return mapping[text]
    m = re.search(r"[1-4]", text)
    return {"1": "I", "2": "II", "3": "III", "4": "IV"}.get(m.group(0), text) if m else text


def build_operational_overlay(monitoring_df: pd.DataFrame,
                              target_by_code_year=None) -> dict:
    """
    Будує «оперативний шар» поверх підтверджених даних.

    Повертає dict: (strat_code, year, quarter) → {
        "record": рядок подання (Series/dict),
        "auto_completed": bool,   # значення ≥ річного орієнтира → ⚡ Виконано
        "status_override": str|None,  # 'Виконано' для авто-зарахованих
    }
    Містить ЛИШЕ записи «після координатора» для періодів, де НЕМАЄ
    підтвердженого запису. target_by_code_year: (code, year) → план року.
    """
    overlay: dict = {}
    if monitoring_df is None or monitoring_df.empty:
        return overlay

    df = monitoring_df.copy()
    for col in ["approval_status", "strat_code", "year", "quarter",
                "numeric_value", "status", "submitted_at",
                "approval_chain", "chain_stage", "object_kind"]:
        if col not in df.columns:
            df[col] = ""

    if "object_kind" in df.columns:
        df = df[df["object_kind"].fillna("measure").astype(str) != "indicator"]

    df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df = df.sort_values("_dt")

    confirmed_keys = set()
    for _, rec in df[df["approval_status"].astype(str).str.strip() == CONFIRMED_STATUS].iterrows():
        confirmed_keys.add((
            _clean(rec.get("strat_code")), _clean(rec.get("year")),
            _quarter_key(rec.get("quarter")),
        ))

    for _, rec in df.iterrows():
        if not is_past_admin(rec):
            continue
        key = (
            _clean(rec.get("strat_code")), _clean(rec.get("year")),
            _quarter_key(rec.get("quarter")),
        )
        if key in confirmed_keys:
            continue  # пріоритет підтверджених — індивідуально по заходу

        target_value = ""
        if target_by_code_year is not None:
            target_value = target_by_code_year.get((key[0], key[1]), "")

        auto_done = target_met(rec.get("numeric_value"), target_value)

        overlay[key] = {
            "record": rec,
            "auto_completed": auto_done,
            "status_override": AUTO_DONE_STATUS if auto_done else None,
        }

    return overlay


def apply_operational_mode(monitoring_df: pd.DataFrame,
                           target_by_code_year=None) -> tuple[pd.DataFrame, list[dict]]:
    """
    Повертає (df_оперативний, перелік_авто_зарахованих) для сторінок, які
    працюють через фільтр approval_status == 'Погоджено':

    df_оперативний — копія monitoring_df, у якій записи «після координатора»
    (для періодів без підтвердженого запису) отримують approval_status =
    'Погоджено', а авто-зараховані — ще й status = 'Виконано'. Кожен такий
    запис маркується колонкою _operational=True / _auto_completed=True.

    Перелік авто-зарахованих: [{code, year, quarter, value, target, stage}].
    """
    if monitoring_df is None or monitoring_df.empty:
        return monitoring_df, []

    df = monitoring_df.copy()
    df["_operational"] = False
    df["_auto_completed"] = False

    overlay = build_operational_overlay(df, target_by_code_year)
    auto_list: list[dict] = []

    if not overlay:
        return df, auto_list

    for col in ["approval_status", "status", "strat_code", "year", "quarter"]:
        if col not in df.columns:
            df[col] = ""

    for idx in df.index:
        rec = df.loc[idx]
        key = (
            _clean(rec.get("strat_code")), _clean(rec.get("year")),
            _quarter_key(rec.get("quarter")),
        )
        item = overlay.get(key)
        if item is None:
            continue
        # Порівнюємо саме той запис (останній «після координатора» за ключем)
        if item["record"].name != idx:
            continue

        df.at[idx, "approval_status"] = CONFIRMED_STATUS
        df.at[idx, "_operational"] = True
        if item["auto_completed"]:
            df.at[idx, "status"] = AUTO_DONE_STATUS
            df.at[idx, "_auto_completed"] = True
            target_value = ""
            if target_by_code_year is not None:
                target_value = target_by_code_year.get((key[0], key[1]), "")
            auto_list.append({
                "code": key[0], "year": key[1], "quarter": key[2],
                "value": _clean(rec.get("numeric_value")),
                "target": _clean(target_value),
                "approval_status": _clean(monitoring_df.loc[idx].get("approval_status")),
            })

    return df, auto_list


def build_target_map(strat_df: pd.DataFrame) -> dict:
    """(code, year) → річний цільовий орієнтир зі стратегічної матриці."""
    result = {}
    if strat_df is None or strat_df.empty:
        return result
    year_cols = {c: c.replace("target_", "") for c in strat_df.columns if str(c).startswith("target_")}
    if "code" not in strat_df.columns:
        return result
    for _, row in strat_df.iterrows():
        code = _clean(row.get("code"))
        if not code:
            continue
        for col, year in year_cols.items():
            result[(code, year)] = _clean(row.get(col))
    return result


def auto_completed_caption(auto_list: list[dict]) -> str:
    """Готовий детальний текст «З них N заходів зараховано автоматично…»."""
    if not auto_list:
        return ""
    n = len(auto_list)
    examples = "; ".join(
        f"{a['code']} ({a['quarter']} кв. {a['year']}: подано {a['value']} при плані {a['target']}, "
        f"етап погодження: «{a['approval_status']}»)"
        for a in auto_list[:5]
    )
    more = f" та ще {n - 5}" if n > 5 else ""
    return (
        f"⚡ З них {n} захід(ів) зараховано системою автоматично: подане значення "
        f"відповідає річному цільовому орієнтиру або краще, але заявка ще перебуває "
        f"на етапі погодження після координатора. Деталі: {examples}{more}."
    )
