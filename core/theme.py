# core/theme.py

"""
Тема системи (правка К7): усі фірмові кольори — в одному місці.

Зараз файл фіксує ПОТОЧНУ палітру системи (нова палітра буде впроваджена
пізніше окремим етапом — тоді зміниться лише цей файл).

Використання:
    from core.theme import COLORS, inject_theme, apply_plotly_theme
"""

from __future__ import annotations

# ── Поточна палітра системи ──
COLORS = {
    "primary":        "#005BBB",
    "primary_dark":   "#032A63",
    "accent_yellow":  "#FFD500",
    "background":     "#F7F9FC",
    "card":           "#FFFFFF",
    "text":           "#132238",
    "text_secondary": "#61708A",
    "border":         "#DCE4F0",
    "success":        "#1E9E57",
    "success_bg":     "#E4F5EC",
    "warning":        "#F4B400",
    "warning_bg":     "#FDF3D8",
    "danger":         "#DC4A4A",
    "danger_bg":      "#FBE5E5",
    "info":           "#4D8DFF",
    "progress":       "#00A8A8",
    "risk":           "#FF7A45",
    "muted":          "#8A96A8",
    "sidebar":        "#032A63",
    "cta_green":      "#118847",
    "cta_green_hover":"#0C713A",
    "btn_secondary":  "#EAF1FF",
    "btn_secondary_hover": "#D9E7FF",
}

# Послідовність кольорів для графіків Plotly (фірмова)
PLOTLY_COLORWAY = [
    "#005BBB", "#00A8A8", "#4D8DFF", "#FF7A45",
    "#1E9E57", "#F4B400", "#8A96A8", "#032A63",
]


def theme_css() -> str:
    """CSS-змінні теми — інжектяться разом із app.css."""
    vars_css = "\n".join(f"    --{k.replace('_', '-')}: {v};" for k, v in COLORS.items())
    return f":root {{\n{vars_css}\n}}"


def inject_theme() -> None:
    import streamlit as st
    st.markdown(f"<style>{theme_css()}</style>", unsafe_allow_html=True)


def apply_plotly_theme() -> None:
    """Фірмовий шаблон Plotly: єдині кольори/шрифти для всіх графіків."""
    try:
        import plotly.graph_objects as go
        import plotly.io as pio
        import plotly.express as px
    except Exception:
        return

    template = go.layout.Template()
    template.layout = go.Layout(
        colorway=PLOTLY_COLORWAY,
        font=dict(family="Segoe UI, Arial, sans-serif", size=12,
                  color=COLORS["text"]),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(title_text=""),
        xaxis=dict(gridcolor="#DCE4F0", zerolinecolor="#DCE4F0"),
        yaxis=dict(gridcolor="#DCE4F0", zerolinecolor="#DCE4F0"),
    )
    pio.templates["mineconomy"] = template
    pio.templates.default = "plotly_white+mineconomy"
    px.defaults.template = "plotly_white+mineconomy"
    px.defaults.color_discrete_sequence = PLOTLY_COLORWAY
