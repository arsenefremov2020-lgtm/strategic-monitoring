from urllib.request import urlopen

SOURCE_URL = "https://raw.githubusercontent.com/arsenefremov2020-lgtm/strategic-monitoring/bdd831a012c57fb55891c31686290c3f58874425/pages/2_%D0%92%D1%96%D0%B7%D1%83%D0%B0%D0%BB%D1%96%D0%B7%D0%B0%D1%86%D1%96%D1%97_%D1%84%D1%96%D0%BD%D0%B0%D0%BB.py"

code = urlopen(SOURCE_URL).read().decode("utf-8")

if "import textwrap" not in code.split("\n")[:20]:
    code = code.replace("import re\n", "import re\nimport textwrap\n", 1)

marker = "# PRESENTATION MODE — PowerPoint-style slides"
head, tail = code.split(marker, 1)

tail = tail.replace(
    "    st.markdown(f\"\"\"\n    <div class=\"pres-overlay\">",
    "    st.markdown(textwrap.dedent(f\"\"\"\n    <div class=\"pres-overlay\">",
    1,
)

tail = tail.replace(
    "    </div>\n    \"\"\", unsafe_allow_html=True)\n    st.stop()",
    "    </div>\n    \"\"\"), unsafe_allow_html=True)\n    st.stop()",
    1,
)

code = head + marker + tail
exec(compile(code, "patched_dashboard.py", "exec"), globals())
