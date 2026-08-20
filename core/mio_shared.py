from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from core.text_utils import names_match, normalize_name

def raw_value(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()



def measure_name_by_code(strat_df: pd.DataFrame) -> dict[str, str]:
    result: dict[str, str] = {}
    if strat_df is None or strat_df.empty or "object_type" not in strat_df.columns:
        return result
    measures = strat_df[strat_df["object_type"] == "measure"]
    for _, row in measures.iterrows():
        code = raw_value(row.get("code"))
        if code and code not in result:
            result[code] = raw_value(row.get("name"))
    return result

def is_empty(value):
    text = raw_value(value).lower().replace(" ", "")
    return text in ["", "nan", "none", "н.д.", "нд", "-", "—"]


def parse_number(value):
    text = raw_value(value)
    if is_empty(text):
        return None
    text = text.replace("\u00a0", " ").replace("%", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in ["", ".", "-", "-."]:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def is_yes_no_unit(unit):
    text = raw_value(unit).lower()
    return "так/ні" in text or ("так" in text and "ні" in text)


def is_positive_yes(value):
    text = raw_value(value).lower()
    return text in ["так", "yes", "y", "true", "1", "виконано"] or text.startswith("так")


def code_sort_key(value):
    """Natural numeric sort for codes like 1., 1.1., 1.1.1."""
    text = raw_value(value)
    nums = re.findall(r"\d+", text)
    if not nums:
        return (9999, text)
    return tuple(int(x) for x in nums) + tuple([0] * max(0, 5 - len(nums)))


ST_DONE     = "Виконано"


ST_PARTIAL  = "Частково виконано"


ST_NOTDONE  = "Не виконано"


ST_NOTYET   = "Не настав час"


ST_OBSOLETE = "Втратило актуальність"


MIO_PERIODS = [
    ("I квартал",   "I"),
    ("I півріччя",  "II"),
    ("9 місяців",   "III"),
    ("РІК",         "IV"),
]


def _quarter_key(value):
    """ЄДИНА реалізація — core.periods.quarter_key (правка К8)."""
    from core.periods import quarter_key
    return quarter_key(value)


def normalize_period_status(value):
    """Shared normalization matching the current core.statuses model categories."""
    t = raw_value(value).lower().replace("’", "'")
    if not t or t in {"nan", "none", "-", "—", "н.д.", "нд"}:
        return ""
    if "втрат" in t and "актуальн" in t:
        return ST_OBSOLETE
    if "не настав" in t or "не настало" in t or "не настане" in t or "термін не настав" in t:
        return ST_NOTYET
    if "частков" in t:
        return ST_PARTIAL
    if ("виконується" in t or "не викон" in t or "не розпоч" in t or "простроч" in t
            or "потребує уваги" in t or "не подано" in t or t == "ні"):
        return ST_NOTDONE
    if t == ST_DONE.lower() or t == "так" or t == "виконано":
        return ST_DONE
    canonical = {x.lower(): x for x in (ST_DONE, ST_PARTIAL, ST_NOTDONE, ST_NOTYET, ST_OBSOLETE)}
    return canonical.get(t, "")


def _plan_is_x(plan):
    return raw_value(plan).strip().lower() == "х"


def mio_fact_plan_ratio(unit, s1, s2, s3, year_fact, plan):
    """
    Точна копія формули Q8 (Співвідношення Факту і Плану, %):

    =ЕСЛИОШИБКА(ЕСЛИ(ИЛИ(I8=$AR$5;K8=$AR$5;M8=$AR$5);"в/а";
       ЕСЛИ(ИЛИ(P8="х";N8="");"х";
          ЕСЛИ($G8="так/ні";ЕСЛИ(И(N8=P8;P8="так");100;0); N8/P8*100)));"х")

    Повертає число (%) або рядок "в/а" / "х".
    """
    try:
        if s1 == ST_OBSOLETE or s2 == ST_OBSOLETE or s3 == ST_OBSOLETE:
            return "в/а"
        if _plan_is_x(plan) or is_empty(year_fact):
            return "х"
        if is_yes_no_unit(unit):
            fact_t = raw_value(year_fact).lower()
            plan_t = raw_value(plan).lower()
            return 100 if (fact_t == plan_t and plan_t == "так") else 0
        fn = parse_number(year_fact)
        pn = parse_number(plan)
        if fn is None or pn in (None, 0):
            return "х"            # IFERROR → "х"
        return fn / pn * 100
    except Exception:
        return "х"


def mio_year_status(unit, s1, s2, s3, year_fact, plan, ratio):
    """
    Точна копія формули O8 (Стан виконання за РІК):

    =ЕСЛИ(ИЛИ(I8=$AR$5;K8=$AR$5;M8=$AR$5);$AR$5;
       ЕСЛИ(ИЛИ(P8="х";N8="");$AR$4;
          ЕСЛИ(G8="так/ні";ЕСЛИ(N8=P8;$AR$1;ЕСЛИ(N8="ні";$AR$3;$AR$4));
             ЕСЛИ(Q8>99,99;$AR$1;ЕСЛИ(И(Q8>74,99;Q8<100);$AR$2;
                ЕСЛИ(Q8=0;$AR$4;$AR$3))))))

    `ratio` — результат mio_fact_plan_ratio() (число або "х"/"в/а").
    """
    if s1 == ST_OBSOLETE or s2 == ST_OBSOLETE or s3 == ST_OBSOLETE:
        return ST_OBSOLETE
    if _plan_is_x(plan) or is_empty(year_fact):
        return ST_NOTYET
    if is_yes_no_unit(unit):
        fact_t = raw_value(year_fact).lower()
        plan_t = raw_value(plan).lower()
        if fact_t == plan_t:
            return ST_DONE
        if fact_t == "ні":
            return ST_NOTDONE
        return ST_NOTYET
    q = ratio
    if not isinstance(q, (int, float)):
        return ST_NOTYET
    if q > 99.99:
        return ST_DONE
    if 74.99 < q < 100:
        return ST_PARTIAL
    if q == 0:
        return ST_NOTYET
    return ST_NOTDONE


_MIO_NAME_GUARD_EXCLUDED = {"count": 0}


def _approved_monitoring_index(monitoring_df, name_map=None):
    """
    Будує індекс погоджених подань: {(strat_code, year, quarter_key) → останній запис}.
    Останній — за submitted_at (як у Excel: остання погоджена відмітка періоду).

    П8 (захист від повторного використання коду): якщо у поданні збережено
    знімок назви заходу (object_name) і він НЕ відповідає поточній назві
    цього коду в Страт_матриці — подання зберігається в базі, але в оцінку
    НЕ враховується (оцінка — «відповідно до нинішніх», як узгоджено).
    Старі записи без object_name враховуються як раніше.
    """
    index = {}
    _MIO_NAME_GUARD_EXCLUDED["count"] = 0
    if monitoring_df is None or monitoring_df.empty:
        return index
    df = monitoring_df.copy()
    for col in ["approval_status", "strat_code", "year", "quarter",
                "status", "numeric_value", "submitted_at", "risks",
                "object_name", "object_kind", "indicator_name"]:
        if col not in df.columns:
            df[col] = ""
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if df.empty:
        return index
    df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df = df.sort_values("_dt")
    for _, rec in df.iterrows():
        # Індекс ЗАХОДІВ: подання індикаторів сюди не потрапляють
        if raw_value(rec.get("object_kind")).lower() == "indicator":
            continue
        code = raw_value(rec.get("strat_code"))
        if name_map is not None:
            stored_name = raw_value(rec.get("object_name"))
            current_name = name_map.get(code)
            if stored_name and current_name is not None                     and not names_match(stored_name, current_name):
                _MIO_NAME_GUARD_EXCLUDED["count"] += 1
                continue
        key = (code, raw_value(rec.get("year")), _quarter_key(rec.get("quarter")))
        index[key] = rec  # пізніший запис перезаписує ранній
    return index


def _approved_indicator_index(monitoring_df):
    """
    П7: окремий індекс подань ІНДИКАТОРІВ цілей/завдань:
    {(code, year, quarter) → {нормалізована назва показника → останній запис}}.
    Порожня назва (старі подання) зберігається під ключем "" (фолбек).
    """
    index = {}
    if monitoring_df is None or monitoring_df.empty:
        return index
    df = monitoring_df.copy()
    for col in ["approval_status", "strat_code", "year", "quarter",
                "numeric_value", "submitted_at", "object_kind", "indicator_name"]:
        if col not in df.columns:
            df[col] = ""
    df = df[df["approval_status"].astype(str).str.strip() == "Погоджено"].copy()
    if df.empty:
        return index
    df["_dt"] = pd.to_datetime(df["submitted_at"], errors="coerce")
    df = df.sort_values("_dt")
    for _, rec in df.iterrows():
        kind = raw_value(rec.get("object_kind")).lower()
        if kind and kind != "indicator":
            continue
        key = (
            raw_value(rec.get("strat_code")),
            raw_value(rec.get("year")),
            _quarter_key(rec.get("quarter")),
        )
        ind_key = normalize_name(rec.get("indicator_name"))
        index.setdefault(key, {})[ind_key] = rec
    return index


def build_mio_measures_table(strat_df, monitoring_df, year):
    """
    Формує таблицю режиму «М_заходи» за один рік.

    Колонки (як в Excel «М_заходи»):
      Стратегічна ціль · Завдання · Захід · Індикатор · Од. виміру ·
      [I квартал: Факт, Стан] · [I півріччя: Факт, Стан] · [9 місяців: Факт, Стан] ·
      [РІК: Факт, Стан(формула)] · План · Співвідношення Факту і Плану, %(формула)

    Квартальні Факт/Стан підтягуються з погоджених подань моніторингу.
    Стан за РІК і Співвідношення обчислюються формулами Excel.
    """
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    mon_index = _approved_monitoring_index(
        monitoring_df, name_map=measure_name_by_code(strat_df))
    plan_col = f"target_{year}"

    rows = []
    for _, m in measures.iterrows():
        code = raw_value(m.get("code"))
        unit = raw_value(m.get("unit"))
        plan = m.get(plan_col, "")

        # Квартальні дані з моніторингу (Факт + нормалізований стан)
        period_fact = {}
        period_status = {}
        for label, qkey in MIO_PERIODS:
            rec = mon_index.get((code, str(year), qkey))
            if rec is not None:
                period_fact[label] = raw_value(rec.get("numeric_value"))
                period_status[label] = normalize_period_status(rec.get("status"))
            else:
                period_fact[label] = ""
                period_status[label] = ""

        s1 = period_status["I квартал"]
        s2 = period_status["I півріччя"]
        s3 = period_status["9 місяців"]
        year_fact = period_fact["РІК"]

        # Формули Excel: спочатку співвідношення (Q8), потім стан за рік (O8)
        ratio = mio_fact_plan_ratio(unit, s1, s2, s3, year_fact, plan)
        year_status = mio_year_status(unit, s1, s2, s3, year_fact, plan, ratio)

        rows.append({
            "Стратегічна ціль": (raw_value(m.get("parent_goal_code")) + " "
                                 + raw_value(m.get("parent_goal_name"))).strip(),
            "Завдання": (raw_value(m.get("parent_task_code")) + " "
                         + raw_value(m.get("parent_task_name"))).strip(),
            "Захід": code,
            "Назва заходу": raw_value(m.get("name")),
            "Індикатор": raw_value(m.get("indicator")),
            "Од. виміру": unit.replace("\n", " ").strip(),
            "Факт · I кв": period_fact["I квартал"],
            "Стан · I кв": s1,
            "Факт · I пів": period_fact["I півріччя"],
            "Стан · I пів": s2,
            "Факт · 9 міс": period_fact["9 місяців"],
            "Стан · 9 міс": s3,
            "Факт · РІК": year_fact,
            "Стан · РІК": year_status,
            "План (ціль. орієнтир)": raw_value(plan),
            "Факт/План, %": ratio,
        })

    return pd.DataFrame(rows)


def rv_period_score(status):
    """
    Бал за квартальний період (формули G8/H8/I8 аркуша «РВ (Заходи)»):

    =ЕСЛИ(М_заходи!I8=$AE$1;$AD$1;
       ЕСЛИ(М_заходи!I8=$AE$4;$AD$4;
          ЕСЛИ(М_заходи!I8=$AE$2;$AD$2;
             ЕСЛИ(М_заходи!I8=$AE$6;$AD$6;$AD$5))))

    `status` — нормалізований стан виконання періоду з «М_заходи».
    Повертає число (1.0 / 0.75 / 0.0) або рядок "х" / "в/а".
    """
    if status == ST_DONE:        # $AE$1
        return 1.0               # $AD$1
    if status == ST_NOTDONE:     # $AE$4
        return 0.0               # $AD$4
    if status == ST_PARTIAL:     # $AE$2
        return 0.75              # $AD$2
    if status == ST_OBSOLETE:    # $AE$6
        return "в/а"             # $AD$6
    return "х"


def rv_year_score(ratio):
    """
    Бал за РІК (формула J8 аркуша «РВ (Заходи)»):

    =ЕСЛИ(М_заходи!Q8="х";"х";
       ЕСЛИ(М_заходи!Q8="в/а";"в/а";М_заходи!Q8/100))

    `ratio` — Співвідношення Факту і Плану, % (Q8 з «М_заходи»).
    Повертає число (частка 0–1+) або рядок "х" / "в/а".
    """
    if ratio == "х":
        return "х"
    if ratio == "в/а":
        return "в/а"
    if isinstance(ratio, (int, float)):
        return ratio / 100.0
    return "х"


def rv_final_result(year_score):
    """
    Кінцевий результат (формула K8 аркуша «РВ (Заходи)»):

    =ЕСЛИ(J8=$AL$5;$AK$5;
       ЕСЛИ(J8=$AL$6;$AK$6;
          ЕСЛИ(J8>=$AL$1;$AK$1;
             ЕСЛИ(И(J8>$AL$2;J8<$AL$1);$AK$2;$AK$4))))

    $AL$5="х" · $AL$6="в/а" · $AL$1=1 · $AL$2=0.75
    `year_score` — результат rv_year_score() (J8).
    Повертає назву стану («Виконано» / «Частково виконано» / …).
    """
    if year_score == "х":                       # =$AL$5
        return ST_NOTYET                        # $AK$5 «Не настав час»
    if year_score == "в/а":                     # =$AL$6
        return ST_OBSOLETE                      # $AK$6 «Втратило актуальність»
    if isinstance(year_score, (int, float)):
        if year_score >= 1.0:                   # >=$AL$1
            return ST_DONE                      # $AK$1 «Виконано»
        if 0.75 < year_score < 1.0:             # И(>$AL$2; <$AL$1)
            return ST_PARTIAL                   # $AK$2 «Частково виконано»
        return ST_NOTDONE                       # $AK$4 «Не виконано» (вкл. рівно 0.75)
    return ST_NOTDONE


def build_rv_measures_table(strat_df, monitoring_df, year):
    """
    Формує таблицю режиму «РВ (Заходи)» за один рік.

    Бере стани з режиму «М_заходи» (G8…I8 ← I8/K8/M8, J8 ← Q8) і
    переводить їх у бали виконання (0–1) та кінцевий результат.

    Колонки (як в Excel «РВ (Заходи)», блок року):
      Захід · Бал I кв (G) · Бал I пів (H) · Бал 9 міс (I) ·
      Бал РІК (J) · Кінцевий результат (K)
    """
    base = build_mio_measures_table(strat_df, monitoring_df, year)
    if base.empty:
        return base

    rows = []
    for _, r in base.iterrows():
        g_q1   = rv_period_score(r["Стан · I кв"])
        h_half = rv_period_score(r["Стан · I пів"])
        i_9m   = rv_period_score(r["Стан · 9 міс"])
        j_year = rv_year_score(r["Факт/План, %"])
        k_res  = rv_final_result(j_year)

        rows.append({
            "Стратегічна ціль": r["Стратегічна ціль"],
            "Завдання":         r["Завдання"],
            "Захід":            r["Захід"],
            "Назва заходу":     r["Назва заходу"],
            "Індикатор":        r["Індикатор"],
            "Од. виміру":       r["Од. виміру"],
            "Бал · I кв":       g_q1,
            "Бал · I пів":      h_half,
            "Бал · 9 міс":      i_9m,
            "Бал · РІК":        j_year,
            "Кінцевий результат": k_res,
        })

    return pd.DataFrame(rows)


RV_PERIOD_COLS = ["Бал · I кв", "Бал · I пів", "Бал · 9 міс", "Бал · РІК"]


def rv_averageif(values):
    """СРЗНАЧЕСЛИ / AVERAGEIF над набором балів періоду.

    Усереднює лише числові бали (0–1), ігноруючи текстові «х»/«в/а».
    Якщо числових немає — повертає «х» (еквівалент ЕСЛИОШИБКА(…;"х")).
    """
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return "х"
    return sum(nums) / len(nums)


def rv_goal_final_result(year_score):
    """Кінцевий результат для СЦ/Завдання за балом РІК (колонка H).

    Відтворює: =ЕСЛИ(H=1;«Виконано»; ЕСЛИ(И(H>0.75;H<1);«Частково виконано»;
                  ЕСЛИ(H="х";«Не настав час»;«Не виконано»)))
    """
    if not isinstance(year_score, (int, float)):    # H = "х"  ($AM$5)
        return ST_NOTYET                             # «Не настав час»
    if year_score >= 1.0 - 1e-9:                     # H = $AM$1 (100%)
        return ST_DONE                               # «Виконано»
    if 0.75 < year_score < 1.0:                      # И(>$AM$2; <$AM$1)
        return ST_PARTIAL                            # «Частково виконано»
    return ST_NOTDONE


def build_rv_goals_table(strat_df, monitoring_df, year):
    """Формує ієрархічну таблицю режиму «РВ (СЦ, Завдання)» за один рік.

    Дворівнева агрегація балів виконання з режиму «РВ (Заходи)»:
      • Завдання      = rv_averageif(балів ЗАХОДІВ із цим префіксом коду)
      • Стратег. ціль = rv_averageif(балів ЗАВДАНЬ із цим префіксом коду)

    Повертає DataFrame у порядку «ціль → її завдання» з колонками:
      Тип · Код · Назва · Бал · I кв · Бал · I пів · Бал · 9 міс ·
      Бал · РІК · Кінцевий результат · К-ть заходів · К-ть завдань
    """
    measures_df = build_rv_measures_table(strat_df, monitoring_df, year)

    # 1) Бали ЗАХОДІВ: код заходу → [I кв, I пів, 9 міс, РІК]
    measure_scores = {}
    if not measures_df.empty:
        for _, m in measures_df.iterrows():
            mcode = raw_value(m["Захід"])
            if mcode:
                measure_scores[mcode] = [m[c] for c in RV_PERIOD_COLS]

    # 2) Довідники цілей і завдань з ієрархії Страт_матриці
    goals = strat_df[strat_df["object_type"] == "goal"][["code", "name"]]
    tasks = strat_df[strat_df["object_type"] == "task"][["code", "name"]]

    # 3) Бали ЗАВДАНЬ = AVERAGEIF за заходами (префікс коду завдання)
    task_scores, task_name, task_meas_cnt = {}, {}, {}
    for _, t in tasks.iterrows():
        tcode = raw_value(t["code"])
        if not tcode or tcode in task_scores:
            continue
        children = [sc for mc, sc in measure_scores.items() if mc.startswith(tcode)]
        task_scores[tcode] = [rv_averageif([c[i] for c in children]) for i in range(4)]
        task_name[tcode] = raw_value(t["name"])
        task_meas_cnt[tcode] = len(children)

    # 4) Бали ЦІЛЕЙ = AVERAGEIF за завданнями (префікс коду цілі)
    goal_scores, goal_name, goal_task_cnt, goal_meas_cnt = {}, {}, {}, {}
    for _, g in goals.iterrows():
        gcode = raw_value(g["code"])
        if not gcode or gcode in goal_scores:
            continue
        child_codes = [tc for tc in task_scores if tc.startswith(gcode)]
        children = [task_scores[tc] for tc in child_codes]
        goal_scores[gcode] = [rv_averageif([c[i] for c in children]) for i in range(4)]
        goal_name[gcode] = raw_value(g["name"])
        goal_task_cnt[gcode] = len(child_codes)
        goal_meas_cnt[gcode] = sum(task_meas_cnt.get(tc, 0) for tc in child_codes)

    # 5) Ієрархічне складання рядків: ціль, далі її завдання
    rows = []
    for gcode in sorted(goal_scores, key=code_sort_key):
        gp = goal_scores[gcode]
        rows.append({
            "Тип": "goal", "Код": gcode, "Назва": goal_name.get(gcode, ""),
            "Бал · I кв": gp[0], "Бал · I пів": gp[1],
            "Бал · 9 міс": gp[2], "Бал · РІК": gp[3],
            "Кінцевий результат": rv_goal_final_result(gp[3]),
            "К-ть заходів": goal_meas_cnt.get(gcode, 0),
            "К-ть завдань": goal_task_cnt.get(gcode, 0),
        })
        for tcode in sorted([tc for tc in task_scores if tc.startswith(gcode)], key=code_sort_key):
            tp = task_scores[tcode]
            rows.append({
                "Тип": "task", "Код": tcode, "Назва": task_name.get(tcode, ""),
                "Бал · I кв": tp[0], "Бал · I пів": tp[1],
                "Бал · 9 міс": tp[2], "Бал · РІК": tp[3],
                "Кінцевий результат": rv_goal_final_result(tp[3]),
                "К-ть заходів": task_meas_cnt.get(tcode, 0),
                "К-ть завдань": 0,
            })

    return pd.DataFrame(rows)


_MIO_GT_TARGET_YEAR = 2028


_MIO_NA = "н.д."


def _mio_gt_branch(fact, base, target, n1, n2):
    """Одна гілка траєкторної оцінки (повторює структуру формули Excel)."""
    rc = (fact / base) ** (1.0 / n1)       # POWER(Факт/база; 1/n1)
    rt = (target / base) ** (1.0 / n2)     # POWER(Ціль/база; 1/n2)
    if target - base < 0:                  # ціль на зниження
        return (100 + (100 - rc * 100)) / (100 + (100 - rt * 100)) * 100
    return rc / rt * 100


def mio_gt_progress_score(is_goal, unit, fact_year, year,
                          f2021, f2024, f2025, target_2028):
    """Значення колонки «Оцінка прогресу у досягненні, %» за один рік.

    Повертає число (%) або рядок «Виконується»/«х»/«» (немає даних).
    """
    # --- бінарний показник «так/ні» ---
    if is_yes_no_unit(unit):
        return "Виконується" if is_positive_yes(fact_year) else "х"

    J = parse_number(fact_year)

    # --- завдання (LEN(код)≠2): простий Факт/Ціль×100 ---
    if not is_goal:
        X = parse_number(target_2028)
        if J is None or X in (None, 0):
            return ""
        return J / X * 100

    # --- ціль (LEN(код)=2): траєкторна формула ---
    if J is None:                          # ЕСЛИ(J="";"")
        return ""
    X = parse_number(target_2028)
    I = parse_number(f2025)
    H = parse_number(f2024)
    G = parse_number(f2021)
    if X in (None, 0):
        return ""

    # I="н.д." (або відсутнє) → база 2024 з фолбеком на 2021 (ЕСЛИОШИБКА)
    if raw_value(f2025).lower() == _MIO_NA or I is None:
        try:
            if H in (None, 0):
                raise ValueError
            return _mio_gt_branch(J, H, X, year - 2024, _MIO_GT_TARGET_YEAR - 2024)
        except (ZeroDivisionError, ValueError, TypeError):
            if G in (None, 0):
                return ""
            return _mio_gt_branch(J, G, X, year - 2021, _MIO_GT_TARGET_YEAR - 2021)

    # звичайний шлях: база = факт 2025 (I). Степені: 1/(рік−2025) та 1/(2028−2025).
    return _mio_gt_branch(J, I, X, year - 2025, _MIO_GT_TARGET_YEAR - 2025)


def mio_gt_change(unit, fact_year, fact_prev):
    """«Зміна до попереднього року, %» = ЕСЛИ(од.=«так/ні»;«х»; Факт/Факт_поп×100)."""
    if is_yes_no_unit(unit):
        return "х"
    f = parse_number(fact_year)
    p = parse_number(fact_prev)
    if f is None or p in (None, 0):
        return ""
    return f / p * 100


def _mio_indicator_year_fact(mon_index, code, year,
                             indicator_name="", ind_index=None):
    """Факт показника за РІК із погоджених подань (Stream 2).

    П7: подання індикаторів тепер зберігають НАЗВУ показника
    (indicator_name), тому для цілей із кількома показниками факт
    підтягується саме до свого показника, а не «розмазується» на всі.
    Старі подання без назви — фолбек на спільний код (як раніше).
    """
    code_v = raw_value(code)
    ind_key = normalize_name(indicator_name)
    # Подані значення індикаторів «станом на дату» лягають у квартал дати
    # подання, тому беремо НАЙНОВІШИЙ доступний квартал року (IV → I).
    for _q in ("IV", "III", "II", "I"):
        if ind_index is not None:
            bucket = ind_index.get((code_v, str(year), _q))
            if bucket:
                rec = bucket.get(ind_key)
                if rec is None and ind_key:
                    rec = bucket.get("")     # старі подання без назви
                if rec is None and not ind_key:
                    if len(bucket) == 1:
                        rec = next(iter(bucket.values()))
                if rec is not None:
                    return raw_value(rec.get("numeric_value"))
        rec = mon_index.get((code_v, str(year), _q))
        if rec is not None:
            # захист: не віддавати факт заходу як факт показника
            kind = raw_value(rec.get("object_kind")).lower()
            if kind in ("", "indicator"):
                return raw_value(rec.get("numeric_value"))
    return ""


_MIO_GT_YEARS = [2026, 2027, 2028]


def build_mio_goals_tasks_table(strat_df, monitoring_df):
    """Формує таблицю режиму «МіО цілі/завдання».

    Один рядок = один показник цілі або завдання (як у «МіО_цілі_завдан»).
    Зберігає ієрархічний порядок «Страт_матриці»: ціль → її показники →
    її завдання → їх показники. Заходи (LEN коду ≥ 5) не входять.
    """
    if strat_df is None or strat_df.empty:
        return pd.DataFrame()

    mon_index = _approved_monitoring_index(monitoring_df)
    ind_index = _approved_indicator_index(monitoring_df)
    goal_types = {"goal", "goal_indicator"}
    task_types = {"task", "task_indicator"}

    rows = []
    for _, r in strat_df.iterrows():
        otype = raw_value(r.get("object_type"))
        if otype not in goal_types and otype not in task_types:
            continue
        indicator = raw_value(r.get("indicator"))
        if not indicator:                  # рядок без показника пропускаємо
            continue

        is_goal = otype in goal_types
        if is_goal:
            code = raw_value(r.get("parent_goal_code")) or raw_value(r.get("code"))
            owner = raw_value(r.get("parent_goal_name"))
        else:
            code = raw_value(r.get("parent_task_code")) or raw_value(r.get("code"))
            owner = raw_value(r.get("parent_task_name"))

        unit = raw_value(r.get("unit")).replace("\n", " ").strip()
        f2021 = raw_value(r.get("base_2021"))
        f2024 = raw_value(r.get("fact_2024"))
        f2025 = raw_value(r.get("fact_2025"))
        target = raw_value(r.get("target_2028_end"))

        entry = {
            "Рівень": "goal" if is_goal else "task",
            "Код": code,
            "Власник": owner,
            "Індикатор": indicator,
            "Од. виміру": unit,
            "Факт 2021": f2021,
            "Факт 2024": f2024,
            "Факт 2025": f2025,
            "Ціль 2028": target,
        }

        prev_fact = f2025                  # попередній для 2026 — факт 2025
        for y in _MIO_GT_YEARS:
            fact_y = _mio_indicator_year_fact(
                mon_index, code, y,
                indicator_name=indicator, ind_index=ind_index)
            entry[f"Факт {y}"] = fact_y
            entry[f"Зміна {y}"] = mio_gt_change(unit, fact_y, prev_fact)
            entry[f"Оцінка {y}"] = mio_gt_progress_score(
                is_goal, unit, fact_y, y, f2021, f2024, f2025, target
            )
            prev_fact = fact_y             # для наступного року попередній — цей факт

        rows.append(entry)

    return pd.DataFrame(rows)


_INT_WEIGHTS = (0.20, 0.30, 0.50)


def _int_is_num(v):
    """Справжнє число (не None, не NaN). NaN з DataFrame має проходити як «порожньо»."""
    return isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v))


def _int_h_value(progress):
    """H-величина за показником = «Оцінка прогресу, %» (M).

    Відтворює Excel H = IFERROR(IF(OR(M="";M=0);"х";M/100);"х"):
    числове ≠ 0 → саме значення (у %); 0, порожнє чи текст («Виконується»/«х»)
    → None (виключається із середніх AVERAGEIF, як текст «х»).
    Масштаб лишаємо у %, бо інтеграл — лінійна зважена сума (×100 наприкінці).
    """
    if _int_is_num(progress) and progress != 0:
        return float(progress)
    return None


def _int_avg(values):
    """AVERAGEIF над H-величинами: лише числа; якщо жодного — None."""
    nums = [v for v in values if _int_is_num(v)]
    return sum(nums) / len(nums) if nums else None


def build_integral_table(strat_df, monitoring_df):
    """Будує дані режиму «Інт_Оцінка».

    Повертає (rows_df, goals_df):
      • rows_df — показникова таблиця (як «МіО_цілі_завдан») з прапорцями-якорями
        та поколонковими значеннями по роках: fact/h/i/j/k/int (None де комірка
        має бути порожньою — тобто не на рядку-якорі);
      • goals_df — зведення по цілях × роки (Інтеграл + компоненти I/J/K) для KPI,
        короткого підсумку й експорту.
    """
    mio = build_mio_goals_tasks_table(strat_df, monitoring_df)
    if mio is None or mio.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 1) Бал РІК виконання заходів по роках (з «РВ (СЦ, Завдання)») → {рік: {код: бал}}
    rv_score = {}
    for y in _MIO_GT_YEARS:
        rvg = build_rv_goals_table(strat_df, monitoring_df, y)
        d = {}
        if rvg is not None and not rvg.empty:
            for _, rr in rvg.iterrows():
                d[raw_value(rr["Код"])] = rr["Бал · РІК"]
        rv_score[y] = d

    goal_rows = mio[mio["Рівень"] == "goal"]
    task_rows = mio[mio["Рівень"] == "task"]
    goal_codes = list(dict.fromkeys(goal_rows["Код"].map(raw_value)))
    task_codes = list(dict.fromkeys(task_rows["Код"].map(raw_value)))

    # 2) Поколонкові агрегати по роках
    goal_K, task_J = {}, {}          # K цілі (власні показники) · J завдання
    goal_I, task_I = {}, {}          # I заходів (бал РІК ×100)
    goal_Jcomp, goal_int = {}, {}    # середнє J завдань цілі · інтеграл
    wI, wJ, wK = _INT_WEIGHTS

    for y in _MIO_GT_YEARS:
        gK, tJ, gI, tI, gJc, gInt = {}, {}, {}, {}, {}, {}

        for tcode in task_codes:
            vals = [_int_h_value(v) for v in
                    task_rows[task_rows["Код"].map(raw_value) == tcode][f"Оцінка {y}"]]
            tJ[tcode] = _int_avg(vals)
            bal = rv_score[y].get(tcode)
            tI[tcode] = bal * 100 if isinstance(bal, (int, float)) else None

        for gcode in goal_codes:
            vals = [_int_h_value(v) for v in
                    goal_rows[goal_rows["Код"].map(raw_value) == gcode][f"Оцінка {y}"]]
            gK[gcode] = _int_avg(vals)
            bal = rv_score[y].get(gcode)
            gI[gcode] = bal * 100 if isinstance(bal, (int, float)) else None
            # середнє J завдань цілі (префікс коду; лише числові J)
            jts = [tJ[tc] for tc in task_codes
                   if tc.startswith(gcode) and isinstance(tJ.get(tc), (int, float))]
            gJc[gcode] = sum(jts) / len(jts) if jts else None
            gInt[gcode] = (wI * (gI[gcode] or 0)
                           + wJ * (gJc[gcode] or 0)
                           + wK * (gK[gcode] or 0))

        goal_K[y], task_J[y] = gK, tJ
        goal_I[y], task_I[y] = gI, tI
        goal_Jcomp[y], goal_int[y] = gJc, gInt

    # 3) Показникові рядки + прапорці-якорі (перший рядок цілі / завдання)
    seen_goal, seen_task = set(), set()
    rows = []
    for _, r in mio.iterrows():
        is_goal = r["Рівень"] == "goal"
        code = raw_value(r["Код"])
        g_anchor = is_goal and code not in seen_goal
        t_anchor = (not is_goal) and code not in seen_task
        if g_anchor:
            seen_goal.add(code)
        if t_anchor:
            seen_task.add(code)

        entry = {
            "Рівень": r["Рівень"], "Код": code, "Власник": r["Власник"],
            "Індикатор": r["Індикатор"], "Од. виміру": r["Од. виміру"],
            "is_goal_anchor": g_anchor, "is_task_anchor": t_anchor,
        }
        for y in _MIO_GT_YEARS:
            entry[f"fact_{y}"] = r[f"Факт {y}"]
            entry[f"h_{y}"] = r[f"Оцінка {y}"]            # відображаємо як прогрес, %
            # I — бал заходів цілі (на якорі цілі) або завдання (на якорі завдання)
            if g_anchor:
                entry[f"i_{y}"] = goal_I[y].get(code)
            elif t_anchor:
                entry[f"i_{y}"] = task_I[y].get(code)
            else:
                entry[f"i_{y}"] = None
            entry[f"j_{y}"] = task_J[y].get(code) if t_anchor else None
            entry[f"k_{y}"] = goal_K[y].get(code) if g_anchor else None
            entry[f"int_{y}"] = goal_int[y].get(code) if g_anchor else None
        rows.append(entry)
    rows_df = pd.DataFrame(rows)

    # 4) Зведення по цілях × роки
    gsum = []
    goal_name = {raw_value(r["Код"]): raw_value(r["Власник"])
                 for _, r in goal_rows.iterrows()}
    for gcode in goal_codes:
        rec = {"Код": gcode, "Ціль": goal_name.get(gcode, "")}
        for y in _MIO_GT_YEARS:
            rec[f"Заходи {y}"] = goal_I[y].get(gcode)
            rec[f"Завдання {y}"] = goal_Jcomp[y].get(gcode)
            rec[f"Прогрес {y}"] = goal_K[y].get(gcode)
            rec[f"Інтеграл {y}"] = goal_int[y].get(gcode)
        gsum.append(rec)
    goals_df = pd.DataFrame(gsum)
    return rows_df, goals_df


FIN_SHEET_CANDIDATES = ["МіО Фінансування", "Фінансування", "БП", "Sheet1", "Аркуш1"]


FIN_CODE_KEYS   = ["код заходу", "код", "захід", "strat_code", "measure_code", "code", "кпкв код"]


FIN_YEAR_KEYS   = ["рік", "year", "звітний рік"]


FIN_KPKVK_KEYS  = ["кпквк", "kpkvk", "kpkv", "код кпквк", "бюджетна програма"]


FIN_SOURCE_KEYS = ["інше джерело фінансування", "інше джерело", "джерело фінансування",
                   "other_source", "fin_source", "джерело"]


FIN_PLAN_KEYS   = ["план (млрд грн)", "план, млрд грн", "план млрд грн", "план млрд",
                   "план", "plan", "fin_plan", "fin_plan_bln"]


FIN_FACT_KEYS   = ["факт (млрд грн)", "факт, млрд грн", "факт млрд грн", "факт млрд",
                   "факт", "fact", "fin_fact", "fin_fact_bln"]


def _fin_norm_header(value):
    """Нормалізує заголовок колонки: нижній регістр, без зайвих пробілів/переносів."""
    t = raw_value(value).lower().replace("\n", " ").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _fin_match_col(columns, candidates):
    """Шукає колонку, чий нормалізований заголовок збігається/містить кандидата."""
    norm = {_fin_norm_header(c): c for c in columns}
    for cand in candidates:                      # точний збіг
        if cand in norm:
            return norm[cand]
    for cand in candidates:                      # частковий збіг (план/факт + рік)
        for nk, orig in norm.items():
            if nk.startswith(cand) or cand in nk:
                return orig
    return None


def _fin_year_columns(columns):
    """Для широкого формату: знаходить пари (рік → колонка плану/факту)."""
    plan_by_year, fact_by_year = {}, {}
    for c in columns:
        nk = _fin_norm_header(c)
        m = re.search(r"(20\d{2})", nk)
        if not m:
            continue
        yr = m.group(1)
        if nk.startswith("план") or "план" in nk:
            plan_by_year[yr] = c
        elif nk.startswith("факт") or "факт" in nk:
            fact_by_year[yr] = c
    return plan_by_year, fact_by_year


def _fin_lookup(fin_index, code, year):
    """Бере бюджетний запис за (код, рік); якщо немає — пробує без року."""
    return (fin_index.get((code, str(year)))
            or fin_index.get((code, ""))
            or {})


def build_financing_table(strat_df, monitoring_df, fin_index, year):
    """
    Формує таблицю режиму «МіО Фінансування» за один рік.

    Колонки:
      Захід (якір: код+назва) · КПКВК · Інше джерело фінансування ·
      План, млрд грн · Факт, млрд грн · % виконання (фін.) ·
      Стан виконання заходу, % · Коефіцієнт еластичності.
    """
    base = build_mio_measures_table(strat_df, monitoring_df, year)
    if base.empty:
        return base

    # Стан виконання заходу = «Бал · РІК» з «РВ (Заходи)» (модель: VLOOKUP,
    # стовпець 7/14/21 для 2026/2027/2028). Бал РІК — частка 0–1 / «х» / «в/а».
    rv = build_rv_measures_table(strat_df, monitoring_df, year)
    rv_year_by_code = {}
    if not rv.empty:
        for _, rr in rv.iterrows():
            rv_year_by_code[rr["Захід"]] = rr["Бал · РІК"]

    # Плановий бюджет, КПКВК та інше джерело — зі Страт_матриці (дані app):
    #   Y=КПКВК · Z/AA/AB=план 2026/2027/2028 · AC=інше джерело.
    plan_col = f"fin_plan_{year}"
    strat_fin = {}
    for _, m in strat_df[strat_df["object_type"] == "measure"].iterrows():
        strat_fin[raw_value(m.get("code"))] = {
            "kpkvk": raw_value(m.get("kpkvk")),
            "other_source": raw_value(m.get("fin_other_source")),
            "plan_bln": parse_number(m.get(plan_col)) if plan_col in m else None,
        }

    rows = []
    for _, r in base.iterrows():
        code = r["Захід"]
        sfin = strat_fin.get(code, {})
        fin = _fin_lookup(fin_index, code, year)   # окремий Excel (факт)

        kpkvk     = sfin.get("kpkvk", "") or fin.get("kpkvk", "")
        other_src = sfin.get("other_source", "") or fin.get("other_source", "")
        # План — пріоритетно зі Страт_матриці; якщо немає, з окремого Excel.
        plan_bln  = sfin.get("plan_bln", None)
        if plan_bln is None:
            plan_bln = fin.get("plan_bln", None)
        # Факт — з окремого Excel «БП під моніторинг СП».
        fact_bln  = fin.get("fact_bln", None)

        # ── Показуємо ЛИШЕ заходи, що мають фінансування ──
        # за держбюджетом (КПКВК або плановий обсяг) АБО за іншим джерелом.
        has_state_budget = bool(kpkvk) or (plan_bln is not None)
        has_other_source = bool(other_src)
        if not (has_state_budget or has_other_source or fact_bln is not None):
            continue  # фінансування немає — захід не відображається

        # % виконання (фін.) = Факт / План (модель: H = G/F). У відсотках (×100).
        if plan_bln not in (None, 0) and fact_bln is not None:
            fin_pct = fact_bln / plan_bln * 100.0
        else:
            fin_pct = None

        # Стан виконання заходу, % = Бал РІК заходу × 100 (частка 0–1 → %).
        rv_year = rv_year_by_code.get(code, "х")
        if isinstance(rv_year, (int, float)):
            state_pct = rv_year * 100.0
        else:
            state_pct = rv_year  # "х" / "в/а"

        # К еластичності = % виконання / стан виконання (модель: J = H/I).
        # IFERROR(IF(H/I; H/I; ""): порожньо при нульовому факті/стані або помилці.
        if (fin_pct not in (None, 0, 0.0)
                and isinstance(state_pct, (int, float)) and state_pct not in (0, 0.0)):
            elasticity = fin_pct / state_pct
        else:
            elasticity = None

        rows.append({
            "Стратегічна ціль": r["Стратегічна ціль"],
            "Завдання":         r["Завдання"],
            "Захід":            code,
            "Назва заходу":     r["Назва заходу"],
            "Індикатор":        r["Індикатор"],
            "Од. виміру":       r["Од. виміру"],
            "КПКВК":            kpkvk,
            "Інше джерело фінансування": other_src,
            "План, млрд грн":   plan_bln,
            "Факт, млрд грн":   fact_bln,
            "% виконання":      fin_pct,
            "Стан виконання заходу, %": state_pct,
            "Коефіцієнт еластичності":  elasticity,
        })

    return pd.DataFrame(rows)

def load_financing_index(path: str | Path = "БП під моніторинг СП.xlsx") -> dict:
    """Pure reusable loader for the financing source used by MіO and Analytics."""
    index: dict = {}
    try:
        xls = pd.ExcelFile(path, engine="openpyxl")
    except Exception:
        return index
    sheet = next((s for s in FIN_SHEET_CANDIDATES if s in xls.sheet_names), xls.sheet_names[0] if xls.sheet_names else None)
    if sheet is None:
        return index
    try:
        df = xls.parse(sheet)
    except Exception:
        return index
    if df is None or df.empty:
        return index
    cols = list(df.columns)
    k_code = _fin_match_col(cols, FIN_CODE_KEYS)
    k_year = _fin_match_col(cols, FIN_YEAR_KEYS)
    k_kpkvk = _fin_match_col(cols, FIN_KPKVK_KEYS)
    k_src = _fin_match_col(cols, FIN_SOURCE_KEYS)
    if not k_code:
        return index
    plan_by_year, fact_by_year = _fin_year_columns(cols)
    wide = (not k_year) and (plan_by_year or fact_by_year)
    if wide:
        for _, rec in df.iterrows():
            code = raw_value(rec.get(k_code))
            if not code:
                continue
            kpkvk = raw_value(rec.get(k_kpkvk)) if k_kpkvk else ""
            src = raw_value(rec.get(k_src)) if k_src else ""
            for yr in set(plan_by_year) | set(fact_by_year):
                plan = parse_number(rec.get(plan_by_year[yr])) if yr in plan_by_year else None
                fact = parse_number(rec.get(fact_by_year[yr])) if yr in fact_by_year else None
                index[(code, yr)] = {"kpkvk": kpkvk, "other_source": src, "plan_bln": plan, "fact_bln": fact}
    else:
        k_plan = _fin_match_col(cols, FIN_PLAN_KEYS)
        k_fact = _fin_match_col(cols, FIN_FACT_KEYS)
        for _, rec in df.iterrows():
            code = raw_value(rec.get(k_code))
            if not code:
                continue
            year = raw_value(rec.get(k_year)) if k_year else ""
            ym = re.search(r"(20\d{2})", year)
            year = ym.group(1) if ym else year
            index[(code, year)] = {
                "kpkvk": raw_value(rec.get(k_kpkvk)) if k_kpkvk else "",
                "other_source": raw_value(rec.get(k_src)) if k_src else "",
                "plan_bln": parse_number(rec.get(k_plan)) if k_plan else None,
                "fact_bln": parse_number(rec.get(k_fact)) if k_fact else None,
            }
    return index


def build_mio_analytics(strat_df: pd.DataFrame, monitoring_df: pd.DataFrame, years: list[int] | tuple[int, ...], financing_path: str | Path = "БП під моніторинг СП.xlsx") -> dict[str, pd.DataFrame]:
    """Reusable MіO analytical outputs without UI or alternative methodology."""
    years = sorted({int(y) for y in years if int(y) in _MIO_GT_YEARS}) or [2026]
    rows_df, goals_df = build_integral_table(strat_df, monitoring_df)
    if not goals_df.empty:
        keep = ["Код", "Ціль"] + [c for c in goals_df.columns if any(c.endswith(f" {y}") for y in years)]
        goals_df = goals_df[[c for c in keep if c in goals_df.columns]].copy()
    # Expose the same measure-level MIO tables as reusable analytical inputs.
    measure_parts=[]
    for year in years:
        part=build_mio_measures_table(strat_df, monitoring_df, year)
        if part is not None and not part.empty:
            part=part.copy(); part["Рік"]=year; measure_parts.append(part)
    measures=pd.concat(measure_parts, ignore_index=True) if measure_parts else pd.DataFrame()

    fin_index = load_financing_index(financing_path)
    fin_parts=[]
    for year in years:
        part=build_financing_table(strat_df, monitoring_df, fin_index, year)
        if part is not None and not part.empty:
            part=part.copy(); part["Рік"]=year; fin_parts.append(part)
    financing=pd.concat(fin_parts, ignore_index=True) if fin_parts else pd.DataFrame()
    gt=build_mio_goals_tasks_table(strat_df, monitoring_df)
    return {"integral_rows": rows_df, "goals": goals_df, "goals_tasks": gt, "measures": measures, "financing": financing}
