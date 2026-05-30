import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(
    page_title="Моніторинг виконання СП",
    layout="wide"
)

FILE_PATH = "Під моніторинг СП.xlsx"
SHEET_NAME = "Страт_матриця"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

st.markdown("""
<style>

.stApp{
background:
linear-gradient(
180deg,
#f4f7fb 0%,
#eef3f8 100%
);
}

.main-title{
font-size:34px;
font-weight:700;
color:#12355B;
margin-bottom:5px;
}

.ministry{
text-align:right;
font-size:14px;
color:#4f5d73;
margin-bottom:20px;
}

.hero-box{
background:#198754;
padding:30px;
border-radius:14px;
color:white;
margin-bottom:25px;
box-shadow:0px 3px 12px rgba(0,0,0,0.08);
}

.hero-title{
font-size:30px;
font-weight:700;
}

.hero-sub{
font-size:16px;
opacity:0.95;
}

.info-box{
background:white;
padding:18px;
border-radius:12px;
border-left:5px solid #12355B;
margin-bottom:18px;
}

.legend{
padding:12px;
border-radius:10px;
background:white;
margin-bottom:20px;
}

.footer{
margin-top:80px;
padding-top:20px;
text-align:center;
font-size:13px;
color:#6c757d;
}

.goal-card{
background:#12355B;
color:white;
padding:16px;
border-radius:12px;
margin-bottom:8px;
font-weight:700;
}

.yellow{
background:#fff3cd;
}

.red{
background:#f8d7da;
}

.normal{
background:white;
}

.measure-card{
padding:10px;
border-radius:8px;
margin-bottom:6px;
border:1px solid #e1e5ea;
}

</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_matrix():

    df = pd.read_excel(
        FILE_PATH,
        sheet_name=SHEET_NAME,
        header=None,
        engine="openpyxl"
    )

    data = df.iloc[7:].copy()

    result = pd.DataFrame({
        "type_marker": data.iloc[:,1],
        "code": data.iloc[:,2],
        "name": data.iloc[:,3],
        "department": data.iloc[:,17]
    })

    result = result.dropna(subset=["code"])

    result["code"] = result["code"].astype(str)

    return result


def load_requests():

    response = (
        supabase
        .table("monitoring_requests")
        .select("*")
        .execute()
    )

    if not response.data:
        return pd.DataFrame()

    return pd.DataFrame(response.data)


matrix = load_matrix()
requests = load_requests()

status_map = {}

if not requests.empty:

    latest = (
        requests
        .sort_values("submitted_at")
        .groupby("strat_code")
        .tail(1)
    )

    for _, row in latest.iterrows():

        status_map[
            str(row["strat_code"])
        ] = str(row["approval_status"])


st.markdown(
"""
<div class='ministry'>
Міністерство економіки, довкілля та сільського господарства України
</div>
""",
unsafe_allow_html=True
)

st.markdown(
"""
<div class='main-title'>
Моніторинг виконання стратегічного плану
</div>
""",
unsafe_allow_html=True
)

st.markdown(
"""
<div class='hero-box'>
<div class='hero-title'>
Внесення квартального моніторингу
</div>

<div class='hero-sub'>
Перейдіть у вкладку "Моніторинг виконання" та подайте інформацію щодо заходів свого департаменту.
</div>
</div>
""",
unsafe_allow_html=True
)

c1,c2,c3,c4 = st.columns(4)

with c1:
    st.metric(
        "Заходів у СП",
        len(matrix)
    )

with c2:
    st.metric(
        "Поданих заявок",
        len(requests)
    )

with c3:

    if not requests.empty:

        approved = len(
            requests[
                requests["approval_status"]
                ==
                "Погоджено"
            ]
        )

    else:
        approved = 0

    st.metric(
        "Погоджено",
        approved
    )

with c4:

    waiting = 0

    if not requests.empty:

        waiting = len(
            requests[
                requests["approval_status"]
                ==
                "Очікує погодження"
            ]
        )

    st.metric(
        "Очікують погодження",
        waiting
    )

st.markdown("""
<div class='info-box'>

<b>Як працювати із системою:</b>

1. Перегляньте структуру стратегічного плану  
2. Перейдіть у вкладку моніторингу  
3. Заповніть квартальні дані  
4. Додайте файли  
5. Подайте на погодження  
6. Перевіряйте статус у вкладці "Мої заявки"

</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class='legend'>

🟨 Подано та очікує погодження  
⚪ Погоджено адміністратором  
🔴 Повернуто на доопрацювання  

</div>
""", unsafe_allow_html=True)

st.subheader("Структура стратегічного плану")

for _, row in matrix.iterrows():

    code = str(row["code"])

    approval = status_map.get(code, "")

    css = "normal"

    if approval == "Очікує погодження":
        css = "yellow"

    elif approval == "Повернуто на доопрацювання":
        css = "red"

    st.markdown(
        f"""
        <div class='measure-card {css}'>

        <b>{code}</b><br>

        {row['name']}

        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
"""
<div class='footer'>

Розроблено департаментом стратегічного планування та макроекономічного прогнозування

</div>
""",
unsafe_allow_html=True
)
