import re
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Dashboard", layout="wide")
st.logo("assets/Мінекономіки.png", size="large")

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Єдине джерело відповідності: Індекс ССП -> Заступник Міністра.
# Має відповідати мапінгу з app.py.
DEPUTY_MINISTER_BY_SSP = {
    "20": "ПИВОВАРОВ Андрій Андрійович", "21": "ПИВОВАРОВ Андрій Андрійович",
    "22": "ПИВОВАРОВ Андрій Андрійович", "23": "ЦИБОРТ Олександр Сергійович",
    "24": "ПИВОВАРОВ Андрій Андрійович", "25": "СОБОЛЕВ Олексій Дмитрович",
    "26": "БЕЗКАРАВАЙНИЙ Ігор Володимирович", "27": "КІНДРАТІВ Віталій Зіновійович",
    "28": "АРТЕМЕНКО Анна Ігорівна", "29": "КІНДРАТІВ Віталій Зіновійович",
    "30": "МАРЧАК Дарія Миколаївна", "31": "ПЕРЕЛИГІН Єгор Євгенович",
    "32": "МАРЧАК Дарія Миколаївна", "33": "АРТЕМЕНКО Анна Ігорівна",
    "34": "ПЕТРУК Віталій Вікторович", "35": "АРТЕМЕНКО Анна Ігорівна",
    "36": "ЦИБОРТ Олександр Сергійович", "37": "МАРЧАК Дарія Миколаївна",
    "38": "КІНДРАТІВ Віталій Зіновійович", "39": "ПЕРЕЛИГІН Єгор Євгенович",
    "40": "ЦИБОРТ Олександр Сергійович", "41": "ПЕТРУК Віталій Вікторович",
    "42": "АРТЕМЕНКО Анна Ігорівна", "43": "МАРЧАК Дарія Миколаївна",
    "44": "КІНДРАТІВ Віталій Зіновійович", "45": "ПИВОВАРОВ Андрій Андрійович",
    "46": "КІНДРАТІВ Віталій Зіновійович", "47": "МАРЧАК Дарія Миколаївна",
    "48": "МАРЧАК Дарія Миколаївна", "49": "АРТЕМЕНКО Анна Ігорівна",
    "50": "СОБОЛЕВ Олексій Дмитрович", "51": "ПИВОВАРОВ Андрій Андрійович",
    "52": "БЕЗКАРАВАЙНИЙ Ігор Володимирович", "54": "ПИВОВАРОВ Андрій Андрійович",
    "55": "ПИВОВАРОВ Андрій Андрійович", "56": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "57": "ПИВОВАРОВ Андрій Андрійович", "58": "ПИВОВАРОВ Андрій Андрійович",
    "59": "СОБОЛЕВ Олексій Дмитрович", "60": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "61": "КІНДРАТІВ Віталій Зіновійович", "62": "ПЕРЕЛИГІН Єгор Євгенович",
    "63": "КРАСНОЛУЦЬКИЙ Олександр Васильович", "64": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "65": "КРАСНОЛУЦЬКИЙ Олександр Васильович", "67": "КРАСНОЛУЦЬКИЙ Олександр Васильович",
    "68": "КРАСНОЛУЦЬКИЙ Олександр Васильович", "69": "ВИСОЦЬКИЙ Тарас Миколайович",
    "70": "ВИСОЦЬКИЙ Тарас Миколайович", "71": "БАШЛИК Денис Олександрович",
    "72": "ВИСОЦЬКИЙ Тарас Миколайович", "73": "БАШЛИК Денис Олександрович",
    "74": "ОВЧАРЕНКО Ірина Іванівна", "75": "ПИВОВАРОВ Андрій Андрійович",
    "76": "ПИВОВАРОВ Андрій Андрійович", "77": "МАРЧАК Дарія Миколаївна",
    "78": "", "79": "", "80": "ВИСОЦЬКИЙ Тарас Миколайович",
}

st.markdown("""
<style>
header[data-testid="stHeader"] {background: transparent !important;}
.stApp {background: #f0f4f9;}
.main .block-container {max-width: 1500px; padding-top: 1rem;}
.ua-stripe {height: 5px; border-radius: 0 0 6px 6px; background: linear-gradient(90deg,#005BBB 50%,#FFD700 50%); margin-bottom: 16px;}
.card {background: #fff; border: 1px solid #dde3ed; border-radius: 14px; padding: 20px 24px; margin-bottom: 18px; box-shadow: 0 2px 12px rgba(0,0,0,.04);}
.title {font-size: 28px; font-weight: 900; color: #0c1a3a; margin-bottom: 6px;}
.subtitle {color: #475569; line-height: 1.55;}
.kpis {display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 12px;}
.kpi {background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px;}
.kpi-l {color: #64748b; font-size: 12px; font-weight: 800; min-height: 32px;}
.kpi-v {color: #0f172a; font-size: 30px; font-weight: 950; line-height: 1;}
</style>
""", unsafe_allow_html=True)


def clean(v):
    if v is None or pd.isna(v) or str(v) == "None":
        return ""
    return str(v).strip()


def indices(v):
    return re.findall(r"\d+", clean(v))


def deputy_by_main_ssp(v):
    idx = indices(v)[0] if indices(v) else ""
    return DEPUTY_MINISTER_BY_SSP.get(idx) or "Не визначено"


def all_ssp_indices(row):
    out = []
    for col in ["department", "department_co_1", "department_co_2"]:
        out += indices(row.get(col, ""))
    return out


def code_sort_key(code):
    parts = re.findall(r"\d+", str(code))
    return tuple(int(p) for p in parts) if parts else (9999,)


def get_goal_code(code):
    p = str(code).split(".")
    return p[0] + "." if p else ""


def parse_period(v):
    t = clean(v).lower()
    if not t or t in {"nan", "none", "н.д.", "нд"}:
        return None
    q = None
    if "1 квартал" in t or "i квартал" in t or " і квартал" in t: q = 1
    elif "2 квартал" in t or "ii квартал" in t or " іі квартал" in t: q = 2
    elif "3 квартал" in t or "iii квартал" in t or " ііі квартал" in t: q = 3
    elif "4 квартал" in t or "iv квартал" in t: q = 4
    y = re.search(r"20\d{2}", t)
    return int(y.group()) * 10 + q if y and q else None


def q_num(q):
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "1": 1, "2": 2, "3": 3, "4": 4}.get(str(q).strip(), 1)


def q_rom(q):
    return {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}.get(str(q).strip(), "I")


def to_number(v):
    t = clean(v).replace(",", ".").replace("%", "")
    if t.lower() in {"", "nan", "none", "н.д.", "нд", "x", "х", "так", "ні", "-", "—"}:
        return None
    m = re.search(r"-?\d+(\.\d+)?", t)
    return float(m.group()) if m else None


def status_display(s):
    m = {"Виконано": "Виконано", "Виконано частково": "Частково виконано", "Частково виконано": "Частково виконано", "Виконується": "Виконується", "Не виконано": "Не виконано", "Прострочено": "Не виконано", "Не розпочато": "Не виконано", "Потребує уваги": "Не виконано", "Не подано": "Не виконано", "Термін не настав": "Термін не настав", "Не настав час": "Термін не настав", "Втратив актуальність": "Втратив актуальність", "Втратило актуальність": "Втратив актуальність"}
    return m.get(clean(s), clean(s) if clean(s) else "Не виконано")


def status_score(s):
    d = status_display(s)
    if d == "Виконано": return 100
    if d == "Частково виконано": return 75
    if d == "Виконується": return 50
    if d in {"Термін не настав", "Втратив актуальність"}: return None
    return 0


def plan_fact(actual, target):
    a, t = to_number(actual), to_number(target)
    if a is not None and t not in (None, 0):
        return round(min(a / t * 100, 150), 1)
    at, tt = clean(actual).lower(), clean(target).lower()
    if tt in {"так", "yes"} or at in {"так", "ні", "yes", "no"}:
        return 100 if at in {"так", "yes"} else 0
    return None


def risk_level(score):
    if score >= 70: return "Критичний ризик"
    if score >= 35: return "Середній ризик"
    return "Низький ризик"


@st.cache_data
def load_strat_matrix():
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=None, engine="openpyxl")
    data = df.iloc[7:].copy()
    def col(i):
        return data.iloc[:, i] if i < data.shape[1] else pd.Series([""] * len(data), index=data.index)
    r = pd.DataFrame({
        "type_marker": col(1), "code": col(2), "name": col(3), "product_type": col(4),
        "indicator": col(5), "unit": col(6), "target_2026": col(10), "target_2027": col(11), "target_2028": col(12),
        "source_national": col(16), "department": col(17), "department_co_1": col(18), "department_co_2": col(19),
        "start_period": col(22), "end_period": col(23),
    }).dropna(subset=["code"])
    r["code"] = r["code"].astype(str).str.strip()
    r["type_marker"] = r["type_marker"].astype(str).str.strip()
    r["deputy_minister"] = r["department"].apply(deputy_by_main_ssp)
    def classify(row):
        marker, code = clean(row["type_marker"]).lower(), clean(row["code"])
        if "стратегічна ціль" in marker: return "goal"
        if "завдання" in marker: return "task"
        if code.count(".") >= 3: return "measure"
        return "other"
    r["object_type"] = r.apply(classify, axis=1)
    return r


@st.cache_data(ttl=60)
def load_requests():
    response = supabase.table("monitoring_requests").select("*").execute()
    return pd.DataFrame(response.data) if response.data else pd.DataFrame()


def period_data(strat_df, requests_df, year, quarter):
    measures = strat_df[strat_df["object_type"] == "measure"].copy()
    goals = strat_df[strat_df["object_type"] == "goal"].copy()
    measures["goal_code"] = measures["code"].apply(get_goal_code)
    measures["strategic_goal"] = measures["goal_code"].map(goals.set_index("code")["name"].to_dict())
    measures["start_num"] = measures["start_period"].apply(parse_period)
    measures["end_num"] = measures["end_period"].apply(parse_period)
    period = int(year) * 10 + q_num(quarter)
    active = measures[(measures["start_num"].isna() | (measures["start_num"] <= period)) & (measures["end_num"].isna() | (measures["end_num"] >= period))].copy()
    need = ["year", "quarter", "strat_code", "status", "numeric_value", "risks", "progress_text", "approval_status", "submitted_at"]
    if requests_df.empty: requests_df = pd.DataFrame(columns=need)
    for c in need:
        if c not in requests_df.columns: requests_df[c] = ""
    approved = requests_df[requests_df["approval_status"].astype(str) == "Погоджено"].copy()
    if approved.empty:
        req = pd.DataFrame(columns=["strat_code", "status", "numeric_value", "risks", "progress_text"])
    else:
        req = approved[(approved["year"].astype(str) == str(year)) & (approved["quarter"].astype(str).isin([str(quarter), str(q_num(quarter)), q_rom(quarter)]))].copy()
        if not req.empty: req = req.sort_values("submitted_at").groupby("strat_code").tail(1)
    active = active.merge(req[["strat_code", "status", "numeric_value", "risks", "progress_text"]], left_on="code", right_on="strat_code", how="left")
    active["status"] = active["status"].fillna("Не подано")
    active["numeric_value"] = active["numeric_value"].fillna("")
    active["selected_target"] = active[f"target_{year}"] if f"target_{year}" in active.columns else ""
    active["status_display"] = active["status"].apply(status_display)
    active["status_score"] = active["status"].apply(status_score)
    active["plan_fact_percent"] = active.apply(lambda x: plan_fact(x["numeric_value"], x["selected_target"]), axis=1)
    active["performance_score"] = active.apply(lambda x: x["plan_fact_percent"] if pd.notna(x["plan_fact_percent"]) else x["status_score"], axis=1)
    active["included_in_assessment"] = ~active["status_display"].isin(["Термін не настав", "Втратив актуальність"])
    active["risk_score"] = active.apply(lambda x: min((45 if x["status"] == "Не подано" else 0) + (45 if (pd.isna(x["performance_score"]) or x["performance_score"] < 75) else 0), 100), axis=1)
    active["auto_risk"] = active["risk_score"].apply(risk_level)
    active.loc[~active["included_in_assessment"], "auto_risk"] = "Не оцінюється"
    active["period_year"], active["period_quarter"] = int(year), q_rom(quarter)
    return active


def build_data(strat_df, requests_df, years, quarters):
    frames = [period_data(strat_df, requests_df, y, q) for y in years for q in quarters]
    frames = [x for x in frames if not x.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def latest_rows(df):
    d = df.copy()
    d["_period_sort"] = d["period_year"].astype(int) * 10 + d["period_quarter"].apply(q_num)
    return d.sort_values(["code", "_period_sort"]).groupby("code", as_index=False).tail(1).drop(columns=["_period_sort"])


def pct(n, total):
    return round(n / total * 100, 1) if total else 0


st.markdown('<div class="ua-stripe"></div>', unsafe_allow_html=True)
st.markdown(f'<div class="card"><div class="title">Аналітичний дашборд результативності стратегічного плану</div><div class="subtitle">Заступник Міністра визначається за мапінгом <b>Індекс ССП → Заступник Міністра</b>. Оновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}</div></div>', unsafe_allow_html=True)

strat_df = load_strat_matrix()
requests_df = load_requests()
measures_all = strat_df[strat_df["object_type"] == "measure"].copy()
measures_all["goal_code"] = measures_all["code"].apply(get_goal_code)

years_options = [2026, 2027, 2028]
quarters_options = ["I", "II", "III", "IV"]
ssp_options = sorted(set(re.findall(r"\d+", " | ".join(measures_all[["department", "department_co_1", "department_co_2"]].fillna("").astype(str).agg(" | ".join, axis=1).tolist()))), key=lambda x: int(x))
deputy_options = sorted(measures_all["deputy_minister"].dropna().astype(str).unique())
goal_options = sorted(measures_all["goal_code"].dropna().astype(str).unique(), key=code_sort_key)
status_options = ["Виконано", "Частково виконано", "Виконується", "Не виконано", "Термін не настав", "Втратив актуальність"]

st.markdown('<div class="card"><b>Параметри відбору</b>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
with c1: years = st.multiselect("Рік", years_options, default=[])
with c2: quarters = st.multiselect("Квартал", quarters_options, default=[])
with c3: selected_ssp = st.multiselect("Індекс ССП", ssp_options, default=[])
with c4: deputies = st.multiselect("Заступник Міністра", deputy_options, default=[])
c5, c6 = st.columns(2)
with c5: statuses = st.multiselect("Статус", status_options, default=[])
with c6: goals = st.multiselect("Стратегічна ціль", goal_options, default=[])
st.markdown('</div>', unsafe_allow_html=True)

active = build_data(strat_df, requests_df, years or years_options, quarters or quarters_options)
if active.empty:
    st.warning("Для обраного періоду активних заходів не знайдено.")
    st.stop()
if selected_ssp:
    active = active[active.apply(lambda r: bool(set(all_ssp_indices(r)).intersection(set(selected_ssp))), axis=1)]
if deputies:
    active = active[active["deputy_minister"].isin(deputies)]
if statuses:
    active = active[active["status_display"].isin(statuses)]
if goals:
    active = active[active["goal_code"].isin(goals)]
active = latest_rows(active)
if active.empty:
    st.warning("За обраними параметрами даних не знайдено.")
    st.stop()

assessed = active[active["included_in_assessment"]].copy()
total = len(active)
submitted = len(active[active["status"] != "Не подано"])
completion = round(assessed["performance_score"].fillna(0).mean(), 1) if not assessed.empty else 0
risk_count = len(assessed[assessed["auto_risk"].isin(["Критичний ризик", "Середній ризик"])])
without_data = len(active[active["status"] == "Не подано"])

st.markdown('<div class="card"><div class="kpis">' + ''.join([
    f'<div class="kpi"><div class="kpi-l">Активних заходів</div><div class="kpi-v">{total}</div></div>',
    f'<div class="kpi"><div class="kpi-l">Подано</div><div class="kpi-v">{submitted}</div><small>{pct(submitted,total)}%</small></div>',
    f'<div class="kpi"><div class="kpi-l">Середнє виконання</div><div class="kpi-v">{completion}%</div></div>',
    f'<div class="kpi"><div class="kpi-l">Ризикових</div><div class="kpi-v">{risk_count}</div><small>{pct(risk_count,len(assessed))}%</small></div>',
    f'<div class="kpi"><div class="kpi-l">Не подано</div><div class="kpi-v">{without_data}</div><small>{pct(without_data,total)}%</small></div>',
]) + '</div></div>', unsafe_allow_html=True)

dep = active.groupby("deputy_minister").agg(Активних_заходів=("code", "count"), Подано=("status", lambda x: (x != "Не подано").sum()), Виконання=("performance_score", "mean"), Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum())).reset_index()
dep["Виконання"] = dep["Виконання"].fillna(0).round(1)
dep = dep.sort_values("Виконання", ascending=True)
st.markdown('<div class="card"><h3>Виконання за Заступниками Міністра</h3>', unsafe_allow_html=True)
fig = px.bar(dep, x="Виконання", y="deputy_minister", orientation="h", text="Виконання", hover_data=["Активних_заходів", "Подано", "Ризикових"], labels={"deputy_minister": "Заступник Міністра", "Виконання": "Середнє виконання, %"})
fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig.update_layout(height=max(420, 38 * len(dep)), margin=dict(l=20, r=70, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig, use_container_width=True)
st.dataframe(dep.sort_values("Активних_заходів", ascending=False), use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)

left, right = st.columns(2)
with left:
    st.markdown('<div class="card"><h3>Статуси виконання</h3>', unsafe_allow_html=True)
    sdata = active.groupby("status_display").size().reset_index(name="Кількість")
    st.plotly_chart(px.pie(sdata, names="status_display", values="Кількість", hole=0.45), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
with right:
    st.markdown('<div class="card"><h3>Ризики</h3>', unsafe_allow_html=True)
    rdata = active.groupby("auto_risk").size().reset_index(name="Кількість")
    st.plotly_chart(px.bar(rdata, x="auto_risk", y="Кількість", text="Кількість"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

gp = active.groupby(["goal_code", "strategic_goal"]).agg(Активних_заходів=("code", "count"), Виконання=("performance_score", "mean"), Ризикових=("auto_risk", lambda x: x.isin(["Критичний ризик", "Середній ризик"]).sum())).reset_index()
gp["Виконання"] = gp["Виконання"].fillna(0).round(1)
gp = gp.sort_values("goal_code", key=lambda s: s.map(code_sort_key))
st.markdown('<div class="card"><h3>Виконання за стратегічними цілями</h3>', unsafe_allow_html=True)
st.plotly_chart(px.bar(gp, x="goal_code", y="Виконання", text="Виконання", hover_data=["strategic_goal", "Активних_заходів", "Ризикових"]), use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

table = active[["code", "name", "department", "department_co_1", "department_co_2", "deputy_minister", "status_display", "performance_score", "auto_risk", "risk_score"]].copy()
table.columns = ["Код", "Захід", "Головний ССП", "Співвиконавець 1", "Співвиконавець 2", "Заступник Міністра", "Статус", "Виконання, %", "Ризик", "Оцінка ризику"]
st.markdown('<div class="card"><h3>Детальна таблиця заходів</h3>', unsafe_allow_html=True)
st.dataframe(table.sort_values("Код", key=lambda s: s.map(code_sort_key)), use_container_width=True, hide_index=True)
st.markdown('</div>', unsafe_allow_html=True)
st.caption("Заступник Міністра визначається за Індексом ССП головного виконавця відповідно до DEPUTY_MINISTER_BY_SSP з app.py.")
