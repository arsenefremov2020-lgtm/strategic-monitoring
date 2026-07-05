# core/exports.py

"""
Спільні інструменти вивантаження (правка №15).

- fig_png_bytes / render_png_download — PNG будь-якого plotly-графіка
  (роздільна «для друку», scale=2) через kaleido;
- register_cyrillic_font / build_presentation_pdf — PDF презентаційного
  режиму Dashboard у фірмовому стилі (reportlab + PNG графіків);
- усі функції деградують коректно: якщо kaleido/reportlab недоступні,
  показується зрозуміла підказка, а сторінка працює далі.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path


# ------------------------------------------------------------
# PNG для plotly-графіків
# ------------------------------------------------------------

def fig_png_bytes(fig, scale: int = 2, width: int | None = None,
                  height: int | None = None) -> bytes | None:
    """PNG-байти plotly-фігури через kaleido; None — якщо kaleido недоступний."""
    try:
        kwargs = {"format": "png", "scale": scale}
        if width:
            kwargs["width"] = width
        if height:
            kwargs["height"] = height
        return fig.to_image(**kwargs)
    except Exception:
        return None


def render_png_download(fig, filename: str, key: str,
                        label: str = "🖼 Завантажити графік (PNG)") -> None:
    """Кнопка завантаження PNG під графіком. Не ламає сторінку без kaleido."""
    import streamlit as st
    png = fig_png_bytes(fig)
    if png is None:
        st.caption(
            "PNG-експорт недоступний: додайте пакет `kaleido` у requirements.txt "
            "та перезапустіть застосунок."
        )
        return
    st.download_button(
        label, data=png,
        file_name=f"{filename}.png", mime="image/png",
        key=key, use_container_width=False,
    )


# ------------------------------------------------------------
# PDF презентаційного режиму
# ------------------------------------------------------------

_CYRILLIC_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

BRAND_BLUE = (0 / 255, 91 / 255, 187 / 255)
BRAND_YELLOW = (255 / 255, 213 / 255, 0 / 255)
DARK = (15 / 255, 23 / 255, 42 / 255)
GREY = (71 / 255, 85 / 255, 105 / 255)


def _register_fonts():
    """Реєструє кириличні шрифти DejaVu; повертає (regular, bold) або None."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        regular_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        bold_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if not regular_path.exists():
            return None
        pdfmetrics.registerFont(TTFont("DejaVu", str(regular_path)))
        if bold_path.exists():
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold_path)))
            return "DejaVu", "DejaVu-Bold"
        return "DejaVu", "DejaVu"
    except Exception:
        return None


def build_presentation_pdf(
    title: str,
    period_text: str,
    kpi_items: list[tuple[str, str]],
    verdict_text: str,
    verdict_level: str,
    insight_lines: list[str],
    figures: list[tuple[str, object]],
    logo_path: str = "assets/Мінекономіки.png",
) -> bytes | None:
    """
    Збирає PDF-презентацію у форматі слайдів 16:9 (як presentation mode):
    титульний слайд → слайд KPI → по слайду на кожен графік → висновок.

    figures: [(назва слайда, plotly_fig), ...]
    verdict_level: "high" | "medium" | "low" (колір плашки висновку).
    Повертає bytes або None (якщо reportlab недоступний).
    """
    try:
        from reportlab.lib.pagesizes import landscape
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdf_canvas
    except Exception:
        return None

    fonts = _register_fonts()
    if fonts is None:
        font_r, font_b = "Helvetica", "Helvetica-Bold"  # запасний варіант
    else:
        font_r, font_b = fonts

    page_w, page_h = 338.7 * mm / 1.27, 190.5 * mm / 1.27  # ~16:9
    page_size = (960, 540)
    page_w, page_h = page_size

    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=page_size)

    def slide_bg():
        c.setFillColorRGB(0.97, 0.98, 0.99)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        c.setFillColorRGB(*BRAND_BLUE)
        c.rect(0, page_h - 8, page_w, 8, fill=1, stroke=0)
        c.setFillColorRGB(*BRAND_YELLOW)
        c.rect(0, page_h - 12, page_w, 4, fill=1, stroke=0)

    def footer(page_no: int):
        c.setFont(font_r, 9)
        c.setFillColorRGB(*GREY)
        c.drawString(30, 16, "Мінекономіки · Система моніторингу стратегічного плану")
        c.drawRightString(page_w - 30, 16, f"Слайд {page_no}")

    def slide_title(text: str):
        c.setFont(font_b, 24)
        c.setFillColorRGB(*DARK)
        c.drawString(40, page_h - 58, text[:80])

    page_no = 1

    # ── Титульний слайд ──
    slide_bg()
    try:
        if Path(logo_path).exists():
            c.drawImage(logo_path, 40, page_h - 170, width=420,
                        preserveAspectRatio=True, anchor="nw", mask="auto")
    except Exception:
        pass
    c.setFont(font_b, 34)
    c.setFillColorRGB(*DARK)
    c.drawString(40, page_h / 2 + 10, title[:60])
    c.setFont(font_r, 18)
    c.setFillColorRGB(*GREY)
    c.drawString(40, page_h / 2 - 26, period_text[:90])
    c.setFont(font_r, 12)
    c.drawString(40, 60, f"Сформовано: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    footer(page_no)
    c.showPage()

    # ── Слайд KPI ──
    page_no += 1
    slide_bg()
    slide_title("Ключові показники")
    cols, card_w, card_h, gap = 4, 205, 120, 18
    x0, y0 = 40, page_h - 110 - card_h
    for i, (label, value) in enumerate(kpi_items[:8]):
        row, col = divmod(i, cols)
        x = x0 + col * (card_w + gap)
        y = y0 - row * (card_h + gap)
        c.setFillColorRGB(1, 1, 1)
        c.roundRect(x, y, card_w, card_h, 12, fill=1, stroke=0)
        c.setFillColorRGB(*BRAND_BLUE)
        c.rect(x, y + card_h - 6, card_w, 6, fill=1, stroke=0)
        c.setFont(font_b, 30)
        c.setFillColorRGB(*DARK)
        c.drawString(x + 16, y + card_h - 58, str(value)[:12])
        c.setFont(font_r, 11)
        c.setFillColorRGB(*GREY)
        # перенос підпису на 2 рядки
        words, line1, line2 = str(label).split(), "", ""
        for w in words:
            if len(line1) + len(w) < 30:
                line1 += (" " if line1 else "") + w
            else:
                line2 += (" " if line2 else "") + w
        c.drawString(x + 16, y + 34, line1[:34])
        if line2:
            c.drawString(x + 16, y + 20, line2[:34])
    footer(page_no)
    c.showPage()

    # ── Слайди-графіки ──
    for fig_title, fig in figures:
        png = fig_png_bytes(fig, scale=2, width=1100, height=560)
        if png is None:
            continue
        page_no += 1
        slide_bg()
        slide_title(fig_title)
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(io.BytesIO(png))
            c.drawImage(img, 40, 50, width=page_w - 80, height=page_h - 140,
                        preserveAspectRatio=True, anchor="c")
        except Exception:
            pass
        footer(page_no)
        c.showPage()

    # ── Слайд висновку ──
    page_no += 1
    slide_bg()
    slide_title("Висновок")
    verdict_colors = {
        "high": (220 / 255, 38 / 255, 38 / 255),
        "medium": (180 / 255, 83 / 255, 9 / 255),
        "low": (21 / 255, 128 / 255, 61 / 255),
    }
    c.setFillColorRGB(*verdict_colors.get(verdict_level, GREY))
    c.roundRect(40, page_h - 150, page_w - 80, 56, 12, fill=1, stroke=0)
    c.setFont(font_b, 16)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(58, page_h - 128, verdict_text[:110])

    c.setFont(font_r, 13)
    c.setFillColorRGB(*DARK)
    y = page_h - 190
    for line in insight_lines[:9]:
        c.drawString(48, y, ("• " + str(line))[:130])
        y -= 24
    footer(page_no)
    c.showPage()

    c.save()
    return buffer.getvalue()


# ------------------------------------------------------------
# Табличні вивантаження заходів (правка К9 — перенесено з app.py)
# ------------------------------------------------------------

def build_measures_export_df(measures, quarter_data, quarter_columns):
    """
    Формує DataFrame вивантаження заходів.

    quarter_columns: список (year, quarter, label) — колонки квартальних
    значень (сторінка передає власний перелік, напр. з get_quarter_columns).
    """
    import pandas as pd
    from core.text_utils import raw_value, strip_leading_code

    rows = []
    for _, measure in measures.iterrows():
        code = raw_value(measure.get("code", ""))
        row = {
            "Код": code,
            "Захід": strip_leading_code(measure.get("name", ""), code),
            "Тип продукту": raw_value(measure.get("product_type", "")),
            "Індикатор": raw_value(measure.get("indicator", "")),
            "Одиниці виміру": raw_value(measure.get("unit", "")),
            "Головний виконавець": raw_value(measure.get("resp_main", "")),
            "Співвиконавець": raw_value(measure.get("resp_co_1", "")),
        }
        for year, quarter, label in quarter_columns:
            key = f"{year}_{quarter}"
            item = quarter_data.get(code, {}).get(key, {})
            row[label] = item.get("value", "")
        rows.append(row)

    return pd.DataFrame(rows)


def dataframe_to_excel_bytes(df, sheet_name: str = "Заходи") -> bytes:
    """DataFrame → байти .xlsx (одна вкладка)."""
    import io as _io
    import pandas as pd  # noqa: F401

    buffer = _io.BytesIO()
    with __import__("pandas").ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()
