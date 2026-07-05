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
    "primary":        "#005BBB",   # головний синій
    "primary_dark":   "#0c2f6e",
    "accent_yellow":  "#FFD500",
    "background":     "#f6f8fc",
    "card":           "#ffffff",
    "text":           "#0f172a",
    "text_secondary": "#475569",
    "border":         "#d8dee9",
    "success":        "#16a34a",
    "success_bg":     "#dcfce7",
    "warning":        "#d97706",
    "warning_bg":     "#fef9c3",
    "danger":         "#dc2626",
    "danger_bg":      "#fee2e2",
    "muted":          "#94a3b8",
}

# Послідовність кольорів для графіків Plotly (фірмова)
PLOTLY_COLORWAY = [
    "#005BBB", "#16a34a", "#d97706", "#dc2626",
    "#7c3aed", "#0891b2", "#be185d", "#4d7c0f",
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
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(title_text=""),
        xaxis=dict(gridcolor="#e8edf5", zerolinecolor="#d8dee9"),
        yaxis=dict(gridcolor="#e8edf5", zerolinecolor="#d8dee9"),
    )
    pio.templates["mineconomy"] = template
    pio.templates.default = "plotly_white+mineconomy"
    px.defaults.template = "plotly_white+mineconomy"
    px.defaults.color_discrete_sequence = PLOTLY_COLORWAY
