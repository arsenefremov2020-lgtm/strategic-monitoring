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

from core.timeutils import now_kyiv
from core.errors import log_cosmetic_error, show_warning


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

_PRES_BG = "#032A63"
_PRES_WHITE = "#FFFFFF"
_PRES_BLUE = "#005BBB"
_PRES_YELLOW = "#FFD500"
_PRES_METRIC_BLUE = "#4D8DFF"
_PRES_TEAL = "#00A8A8"
_PRES_ORANGE = "#FF7A45"
_PRES_AMBER = "#F4B400"
_PRES_GREY = "#8A96A8"
_PRES_RED = "#DC4A4A"
_PRES_GREEN = "#118847"
_PRES_BRIGHT_GREEN = "#1E9E57"

# Legacy generic renderer colors retained for the existing MIO consumer.
BRAND_BLUE = (0 / 255, 91 / 255, 187 / 255)
BRAND_YELLOW = (255 / 255, 213 / 255, 0 / 255)
DARK = (15 / 255, 23 / 255, 42 / 255)
GREY = (71 / 255, 85 / 255, 105 / 255)


def _register_fonts():
    """Register bundled/system DejaVu fonts so Ukrainian text is deterministic."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        candidates = [
            (Path("assets/fonts/DejaVuSans.ttf"), Path("assets/fonts/DejaVuSans-Bold.ttf")),
            (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        ]
        for regular_path, bold_path in candidates:
            if not regular_path.exists():
                continue
            pdfmetrics.registerFont(TTFont("DejaVu", str(regular_path)))
            if bold_path.exists():
                pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold_path)))
                return "DejaVu", "DejaVu-Bold"
            return "DejaVu", "DejaVu"
        return None
    except Exception:
        return None


def build_legacy_presentation_pdf(
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
    Legacy generic PDF renderer retained only for non-Dashboard consumers:
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
    except Exception as exc:
        log_cosmetic_error("Додавання логотипа до PDF-презентації", exc)
    c.setFont(font_b, 34)
    c.setFillColorRGB(*DARK)
    c.drawString(40, page_h / 2 + 10, title[:60])
    c.setFont(font_r, 18)
    c.setFillColorRGB(*GREY)
    c.drawString(40, page_h / 2 - 26, period_text[:90])
    c.setFont(font_r, 12)
    c.drawString(40, 60, f"Сформовано: {now_kyiv().strftime('%d.%m.%Y %H:%M')}")
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
        except Exception as exc:
            log_cosmetic_error("Додавання графіка до PDF-презентації", exc)
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


def build_presentation_pdf(presentation_payload: dict) -> bytes | None:
    """Render the canonical seven-slide Dashboard presentation payload as PDF.

    No Dashboard analytics are recalculated here. The renderer only consumes
    display-ready values, ordering and rows prepared by Presentation mode.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen import canvas as pdf_canvas
    except Exception:
        return None

    from core.presentation import validate_presentation_payload

    validate_presentation_payload(presentation_payload)
    fonts = _register_fonts()
    font_r, font_b = fonts if fonts is not None else ("Helvetica", "Helvetica-Bold")

    page_w, page_h = 960, 540
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=(page_w, page_h))

    def rgb(value):
        value = str(value or "#000000").lstrip("#")
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def blend(fg, alpha, bg=_PRES_BG):
        fr, fg_, fb = rgb(fg)
        br, bg_, bb = rgb(bg)
        return (
            br * (1 - alpha) + fr * alpha,
            bg_ * (1 - alpha) + fg_ * alpha,
            bb * (1 - alpha) + fb * alpha,
        )

    def set_fill(value):
        c.setFillColorRGB(*rgb(value))

    def set_stroke(value):
        c.setStrokeColorRGB(*rgb(value))

    unsupported = (
        "🇺🇦", "🔴", "🟡", "🟢", "ℹ️", "📅", "🗓", "🏢", "📌", "🕐",
        "📋", "📊", "🎯", "⬆", "⛶", "✕",
    )

    def clean_text(value):
        text = str(value if value is not None else "")
        for token in unsupported:
            text = text.replace(token, "")
        return text.replace("\ufe0f", "").strip()

    def wrap_lines(text, font_name, font_size, max_width):
        paragraphs = clean_text(text).splitlines() or [""]
        lines = []
        for paragraph in paragraphs:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            line = ""
            for word in words:
                candidate = word if not line else f"{line} {word}"
                if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                    line = ""
                if pdfmetrics.stringWidth(word, font_name, font_size) <= max_width:
                    line = word
                    continue
                part = ""
                for ch in word:
                    candidate = part + ch
                    if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                        part = candidate
                    else:
                        if part:
                            lines.append(part)
                        part = ch
                line = part
            if line:
                lines.append(line)
        return lines or [""]

    def draw_wrapped(
        text, x, y, max_width, *, font=font_r, size=13, leading=None,
        color=_PRES_WHITE, max_lines=None, ellipsis=False,
    ):
        leading = leading or size * 1.35
        lines = wrap_lines(text, font, size, max_width)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            if ellipsis and lines:
                last = lines[-1].rstrip("… ")
                while last and pdfmetrics.stringWidth(last + "…", font, size) > max_width:
                    last = last[:-1]
                lines[-1] = last.rstrip() + "…"
        set_fill(color)
        c.setFont(font, size)
        current_y = y
        for line in lines:
            c.drawString(x, current_y, line)
            current_y -= leading
        return current_y, len(lines)

    def slide_bg():
        set_fill(_PRES_BG)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    def slide_num(page_no):
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.20))
        c.setFont(font_b, 11)
        c.drawRightString(page_w - 40, page_h - 31, f"{page_no:02d} / 07")

    def section_heading(section, title, subtitle=""):
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.35))
        c.setFont(font_b, 11)
        c.drawString(64, 464, clean_text(section).upper())
        draw_wrapped(title, 64, 424, 820, font=font_b, size=31, leading=35, max_lines=2)
        if subtitle:
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.40))
            c.setFont(font_r, 13)
            c.drawString(64, 382, clean_text(subtitle))

    def card_rect(x, y, w, h, *, border_alpha=0.08, fill_alpha=0.04, radius=12):
        c.setFillColorRGB(*blend(_PRES_WHITE, fill_alpha))
        c.setStrokeColorRGB(*blend(_PRES_WHITE, border_alpha))
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, radius, fill=1, stroke=1)

    def draw_metric_bar(x, y, label, value, value_text, color, width=430):
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.55))
        c.setFont(font_b, 12)
        c.drawString(x, y + 3, clean_text(label))
        track_x = x + 220
        track_w = width
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.06))
        c.roundRect(track_x, y, track_w, 10, 5, fill=1, stroke=0)
        try:
            pct = min(max(float(value or 0), 0), 100)
        except (TypeError, ValueError):
            pct = 0
        if pct > 0:
            set_fill(color)
            c.roundRect(track_x, y, track_w * pct / 100.0, 10, 5, fill=1, stroke=0)
        set_fill(_PRES_WHITE)
        c.setFont(font_b, 13)
        c.drawRightString(track_x + track_w + 88, y - 1, clean_text(value_text))

    def render_title(slide):
        # Vector Ukrainian flag avoids unsupported emoji glyphs.
        flag_x, flag_y, flag_w, flag_h = 64, 470, 20, 12
        set_fill(_PRES_BLUE)
        c.rect(flag_x, flag_y + flag_h / 2, flag_w, flag_h / 2, fill=1, stroke=0)
        set_fill(_PRES_YELLOW)
        c.rect(flag_x, flag_y, flag_w, flag_h / 2, fill=1, stroke=0)
        set_fill(_PRES_YELLOW)
        c.setFont(font_b, 11)
        c.drawString(92, 470, clean_text(slide.get("eyebrow", "")).upper())

        y, _ = draw_wrapped(
            slide.get("title", ""), 64, 408, 820,
            font=font_b, size=42, leading=46, max_lines=3, ellipsis=True,
        )
        y -= 8
        y, _ = draw_wrapped(
            slide.get("subtitle", ""), 64, y, 620,
            font=font_r, size=15, leading=24, color="#8799B6", max_lines=4,
        )
        pills = list(slide.get("filter_pills") or [])
        x, py = 64, max(78, y - 24)
        for pill in pills:
            text = clean_text(pill)
            w = pdfmetrics.stringWidth(text, font_b, 11) + 26
            if x + w > page_w - 64:
                x = 64
                py -= 34
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.06))
            c.setStrokeColorRGB(*blend(_PRES_WHITE, 0.12))
            c.roundRect(x, py, w, 26, 13, fill=1, stroke=1)
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.70))
            c.setFont(font_b, 11)
            c.drawString(x + 13, py + 8, text)
            x += w + 10

    def render_verdict(slide):
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.35))
        c.setFont(font_b, 11)
        c.drawString(64, 464, clean_text(slide.get("section", "")).upper())
        severity = str(slide.get("severity") or "medium")
        accent = {"high": _PRES_RED, "medium": _PRES_AMBER, "low": _PRES_GREEN}.get(severity, _PRES_AMBER)
        title = clean_text(slide.get("title", ""))
        badge_w = min(780, pdfmetrics.stringWidth(title, font_b, 23) + 68)
        c.setFillColorRGB(*blend(accent, 0.18))
        set_stroke(accent)
        c.setLineWidth(1.5)
        c.roundRect(64, 393, badge_w, 50, 10, fill=1, stroke=1)
        set_fill(accent)
        c.circle(84, 418, 6, fill=1, stroke=0)
        c.setFont(font_b, 23)
        c.drawString(102, 410, title)

        body_y, line_count = draw_wrapped(
            slide.get("text", ""), 64, 365, 700,
            font=font_r, size=14, leading=21, color="#8DA0BB",
        )
        cards_y = min(184, body_y - 20)
        cards_y = max(cards_y, 82)
        cards = list(slide.get("cards") or [])
        gap = 16
        card_w = (700 - gap * 2) / 3
        for i, item in enumerate(cards[:3]):
            x = 64 + i * (card_w + gap)
            card_rect(x, cards_y, card_w, 98)
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.35))
            c.setFont(font_b, 10)
            c.drawString(x + 16, cards_y + 72, clean_text(item.get("label", "")).upper())
            set_fill(item.get("color") or _PRES_WHITE)
            c.setFont(font_b, 31)
            c.drawString(x + 16, cards_y + 37, clean_text(item.get("value_text", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.35))
            c.setFont(font_r, 9.5)
            draw_wrapped(item.get("subtitle", ""), x + 16, cards_y + 18, card_w - 32,
                         font=font_r, size=9.5, leading=12, color="#788AA5", max_lines=2)

    def render_key_metrics(slide):
        section_heading(slide.get("section", ""), slide.get("title", ""), slide.get("subtitle", ""))
        cards = list(slide.get("cards") or [])
        cols, gap, card_h = 4, 14, 74
        card_w = (page_w - 128 - gap * 3) / cols
        top_y = 280
        for i, item in enumerate(cards[:8]):
            row, col = divmod(i, cols)
            x = 64 + col * (card_w + gap)
            y = top_y - row * (card_h + 12)
            card_rect(x, y, card_w, card_h)
            accent = item.get("color") or _PRES_METRIC_BLUE
            set_fill(accent)
            c.rect(x, y + card_h - 3, card_w, 3, fill=1, stroke=0)
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.40))
            c.setFont(font_b, 9)
            label_lines = wrap_lines(item.get("label", ""), font_b, 9, card_w - 24)[:2]
            ly = y + card_h - 20
            for line in label_lines:
                c.drawString(x + 12, ly, line.upper())
                ly -= 11
            set_fill(_PRES_WHITE)
            c.setFont(font_b, 24)
            c.drawString(x + 12, y + 22, clean_text(item.get("value_text", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.35))
            c.setFont(font_b, 9)
            c.drawRightString(x + card_w - 12, y + 12, clean_text(item.get("sub_text", "")))

        bar_y = 156
        for item in list(slide.get("bars") or [])[:4]:
            draw_metric_bar(
                64, bar_y, item.get("label", ""), item.get("value"),
                item.get("value_text", ""), item.get("color") or _PRES_BLUE, width=430,
            )
            bar_y -= 31

    def render_goals(slide):
        section_heading(slide.get("section", ""), slide.get("title", ""), slide.get("subtitle", ""))
        rows = list(slide.get("rows") or [])
        if not rows:
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
            c.setFont(font_r, 13)
            c.drawString(64, 330, clean_text(slide.get("empty_text", "Дані відсутні за обраними фільтрами")))
            return
        available = 300
        step = min(38, available / max(len(rows), 1))
        y = 344
        for row in rows:
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.40))
            c.setFont(font_b, 10)
            c.drawRightString(98, y, clean_text(row.get("code", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.70))
            c.setFont(font_r, 11)
            name = clean_text(row.get("name", ""))
            c.drawString(114, y, name)
            track_x, track_w = 460, 360
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.06))
            c.roundRect(track_x, y - 1, track_w, 9, 4.5, fill=1, stroke=0)
            try:
                pct = min(max(float(row.get("value") or 0), 0), 100)
            except (TypeError, ValueError):
                pct = 0
            if pct > 0:
                set_fill(row.get("color") or _PRES_GREY)
                c.roundRect(track_x, y - 1, track_w * pct / 100.0, 9, 4.5, fill=1, stroke=0)
            set_fill(_PRES_WHITE)
            c.setFont(font_b, 11)
            c.drawRightString(878, y, clean_text(row.get("value_text", "")))
            y -= step

    def render_risks(slide):
        section_heading(slide.get("section", ""), slide.get("title", ""), slide.get("subtitle", ""))
        cards = list(slide.get("cards") or [])
        gap, card_w, card_h = 18, 260, 118
        x0, y = 64, 238
        accents = [_PRES_RED, _PRES_AMBER, _PRES_BRIGHT_GREEN]
        for i, item in enumerate(cards[:3]):
            x = x0 + i * (card_w + gap)
            accent = item.get("color") or accents[i]
            c.setFillColorRGB(*blend(accent, 0.10))
            c.setStrokeColorRGB(*blend(accent, 0.30))
            c.roundRect(x, y, card_w, card_h, 14, fill=1, stroke=1)
            set_fill(accent)
            c.setFont(font_b, 9.5)
            lines = wrap_lines(item.get("label", ""), font_b, 9.5, card_w - 28)[:2]
            ly = y + 91
            for line in lines:
                c.drawString(x + 14, ly, line.upper())
                ly -= 12
            c.setFont(font_b, 36)
            c.drawString(x + 14, y + 37, clean_text(item.get("value_text", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.40))
            c.setFont(font_b, 9.5)
            c.drawString(x + 14, y + 18, clean_text(item.get("sub_text", "")))

        panel_y, panel_h = 58, 146
        card_rect(64, panel_y, 650, panel_h, border_alpha=0.07, fill_alpha=0.03, radius=14)
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
        c.setFont(font_b, 10)
        c.drawString(88, panel_y + panel_h - 25, clean_text(slide.get("summary_label", "")).upper())
        draw_wrapped(
            slide.get("summary_text", ""), 88, panel_y + panel_h - 48, 602,
            font=font_r, size=12, leading=17, color="#A3B1C6", max_lines=5, ellipsis=False,
        )
        tags = list(slide.get("tags") or [])
        tx = 88
        for tag in tags[:2]:
            text = clean_text(tag)
            w = pdfmetrics.stringWidth(text, font_b, 9.5) + 22
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.06))
            c.setStrokeColorRGB(*blend(_PRES_WHITE, 0.10))
            c.roundRect(tx, panel_y + 14, w, 24, 6, fill=1, stroke=1)
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.50))
            c.setFont(font_b, 9.5)
            c.drawString(tx + 11, panel_y + 22, text)
            tx += w + 10

    def render_top5(slide):
        section_heading(slide.get("section", ""), slide.get("title", ""), slide.get("subtitle", ""))
        rows = list(slide.get("rows") or [])
        if not rows:
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
            c.setFont(font_r, 13)
            c.drawString(64, 330, clean_text(slide.get("empty_text", "Критичних заходів не виявлено")))
            return
        y = 335
        for row in rows[:5]:
            color = row.get("risk_color") or _PRES_GREY
            badge_text = clean_text(row.get("risk_label", ""))
            bw = min(150, pdfmetrics.stringWidth(badge_text, font_b, 8.5) + 18)
            set_fill(color)
            c.roundRect(64, y - 4, bw, 22, 6, fill=1, stroke=0)
            set_fill(_PRES_BG)
            c.setFont(font_b, 8.5)
            c.drawString(73, y + 3, badge_text)
            name_x = 64 + bw + 16
            draw_wrapped(row.get("name", ""), name_x, y + 10, 720 - bw,
                         font=font_b, size=11, leading=14, color="#D5DCE7", max_lines=2, ellipsis=True)
            meta = (
                f'{clean_text(row.get("code", ""))}  ·  '
                f'{clean_text(row.get("department", ""))}  ·  '
                f'{clean_text(row.get("status", ""))}  ·  '
                f'Виконання: {clean_text(row.get("performance_text", ""))}'
            )
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.35))
            c.setFont(font_r, 8.5)
            c.drawString(name_x, y - 21, meta)
            c.setStrokeColorRGB(*blend(_PRES_WHITE, 0.06))
            c.line(64, y - 34, 900, y - 34)
            y -= 62

    def render_finance(slide):
        section_heading(slide.get("section", ""), slide.get("title", ""), slide.get("subtitle", ""))
        left_x, right_x = 64, 520
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
        c.setFont(font_b, 10)
        c.drawString(left_x, 348, clean_text(slide.get("sources_label", "")).upper())
        y = 315
        for item in list(slide.get("groups") or [])[:4]:
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.70))
            c.setFont(font_b, 11)
            c.drawString(left_x, y + 8, clean_text(item.get("label", "")))
            set_fill(_PRES_WHITE)
            c.drawRightString(left_x + 390, y + 8, clean_text(item.get("display", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.07))
            c.roundRect(left_x, y - 7, 390, 9, 4.5, fill=1, stroke=0)
            try:
                pct = min(max(float(item.get("percent") or 0), 0), 100)
            except (TypeError, ValueError):
                pct = 0
            if pct > 0:
                set_fill(item.get("color") or _PRES_GREY)
                c.roundRect(left_x, y - 7, 390 * pct / 100.0, 9, 4.5, fill=1, stroke=0)
            y -= 48

        budget = dict(slide.get("budget") or {})
        c.setFillColorRGB(*blend(_PRES_BLUE, 0.12))
        c.setStrokeColorRGB(*blend(_PRES_BLUE, 0.25))
        c.roundRect(left_x, 70, 390, 102, 12, fill=1, stroke=1)
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
        c.setFont(font_b, 10)
        c.drawString(left_x + 18, 144, clean_text(budget.get("label", "")).upper())
        set_fill(_PRES_WHITE)
        c.setFont(font_b, 28)
        c.drawString(left_x + 18, 108, clean_text(budget.get("value_text", "")))
        c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
        c.setFont(font_r, 9.5)
        c.drawString(left_x + 18, 86, clean_text(budget.get("subtitle", "")))

        c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
        c.setFont(font_b, 10)
        c.drawString(right_x, 348, clean_text(slide.get("kpkvk_label", "")).upper())
        rows = list(slide.get("kpkvk_rows") or [])
        if not rows:
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.30))
            c.setFont(font_r, 12)
            c.drawString(right_x, 315, clean_text(slide.get("kpkvk_empty_text", "КПКВК не визначено")))
            return
        y = 315
        for row in rows[:6]:
            set_fill(_PRES_YELLOW)
            c.setFont(font_b, 12)
            c.drawString(right_x, y, clean_text(row.get("code", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.50))
            c.setFont(font_r, 10)
            c.drawString(right_x + 110, y, clean_text(row.get("count_text", "")))
            c.setFillColorRGB(*blend(_PRES_WHITE, 0.70))
            c.setFont(font_b, 10)
            c.drawRightString(900, y, clean_text(row.get("budget_text", "")))
            c.setStrokeColorRGB(*blend(_PRES_WHITE, 0.06))
            c.line(right_x, y - 13, 900, y - 13)
            y -= 43

    renderers = {
        "title": render_title,
        "verdict": render_verdict,
        "key_metrics": render_key_metrics,
        "strategic_goals": render_goals,
        "risks": render_risks,
        "top5": render_top5,
        "finance": render_finance,
    }

    for page_no, slide in enumerate(presentation_payload["slides"], start=1):
        slide_bg()
        slide_num(page_no)
        renderers[slide["key"]](slide)
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
    """DataFrame → байти .xlsx (одна вкладка), з охайним оформленням.

    Тонкий зручний виклик поверх write_styled_excel — лишений для
    сумісності з існуючими викликами (app.py тощо), але тепер теж
    видає красиво оформлений файл, а не голий df.to_excel().
    """
    return write_styled_excel({sheet_name: df})


# ------------------------------------------------------------
# Охайне оформлення Excel-вивантажень (пункт запиту:
# "Зроби нормальні експорти в ексель... щоб воно вивантажувалося
# так само гарно як і ексель Під моніторинг СП")
# ------------------------------------------------------------
#
# Раніше практично кожне вивантаження в системі (app.py, Аналітика,
# Журнал дій) робило голий df.to_excel(writer, ...) — без жодного
# форматування: ані ширини колонок, ані закріпленої шапки, ані меж
# клітинок. write_styled_excel() — єдина спільна функція, яка тепер
# застосовується всюди: жирна темна шапка з білим текстом (той самий
# візуальний стиль, що й у "Під моніторинг СП.xlsx" — колір #032A63),
# закріplena шапка, автофільтр, розумна ширина колонок за вмістом,
# перенос тексту в довгих колонках, тонкі межі й легке "зебра"-заливання
# рядків для зручного читання великих вивантажень.

_HEADER_BG = "#032A63"
_HEADER_FG = "#FFFFFF"
_BORDER_COLOR = "#DCE4F0"
_BAND_BG = "#F7F9FC"

_MIN_COL_WIDTH = 10
_MAX_COL_WIDTH = 60
_WRAP_WIDTH_THRESHOLD = 38


def _estimate_column_width(series) -> int:
    """Приблизна ширина колонки за вмістом (символи), з розумними межами."""
    try:
        header_len = len(str(series.name))
    except Exception:
        header_len = _MIN_COL_WIDTH

    try:
        non_empty = series.dropna().astype(str)
        max_len = int(non_empty.map(len).max()) if len(non_empty) else header_len
    except Exception:
        max_len = header_len

    width = max(header_len, max_len) + 2
    return max(_MIN_COL_WIDTH, min(width, _MAX_COL_WIDTH))


def write_styled_excel(
    sheets: dict,
    *,
    freeze_first_col: int = 0,
    extra_sheets_no_style: dict | None = None,
) -> bytes:
    """
    Формує .xlsx з кількох аркушів із єдиним охайним оформленням.

    sheets: {назва_аркуша: DataFrame} — кожен аркуш отримує:
      - жирну темну шапку з білим текстом, по центру, з переносом;
      - закріплений перший рядок (і, за потреби, перші freeze_first_col
        колонок — зручно для широких таблиць на кшталт "Заходів", де
        хочеться завжди бачити код/назву під час горизонтальної прокрутки);
      - автофільтр на шапці;
      - ширину колонок за вмістом (у розумних межах);
      - тонкі межі й перенос тексту в довгих текстових колонках;
      - легке почергове заливання рядків для зручності читання.

    extra_sheets_no_style: {назва_аркуша: DataFrame} — додаткові аркуші
    (напр. "Параметри вивантаження"), які пишуться як є, без цього
    оформлення (короткі службові таблиці "параметр — значення").
    """
    import io
    import pandas as pd

    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book

        header_fmt = workbook.add_format({
            "bold": True, "font_color": _HEADER_FG, "bg_color": _HEADER_BG,
            "align": "center", "valign": "vcenter", "text_wrap": True,
            "border": 1, "border_color": "#FFFFFF",
        })
        cell_fmt = workbook.add_format({
            "valign": "top", "border": 1, "border_color": _BORDER_COLOR,
        })
        cell_wrap_fmt = workbook.add_format({
            "valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR,
        })
        band_fmt = workbook.add_format({
            "valign": "top", "border": 1, "border_color": _BORDER_COLOR, "bg_color": _BAND_BG,
        })
        band_wrap_fmt = workbook.add_format({
            "valign": "top", "text_wrap": True, "border": 1,
            "border_color": _BORDER_COLOR, "bg_color": _BAND_BG,
        })

        def _fmt_for(row_idx: int, wrap: bool):
            banded = (row_idx % 2 == 0)  # парні рядки даних — легке заливання
            if wrap:
                return band_wrap_fmt if banded else cell_wrap_fmt
            return band_fmt if banded else cell_fmt

        for sheet_name, df in (sheets or {}).items():
            safe_name = str(sheet_name)[:31] or "Аркуш"
            df = df if df is not None else pd.DataFrame()
            n_rows, n_cols = df.shape

            worksheet = workbook.add_worksheet(safe_name)
            writer.sheets[safe_name] = worksheet

            if n_cols == 0:
                worksheet.write(0, 0, "Немає даних для вивантаження", header_fmt)
                continue

            wrap_flags = []
            for col_idx, col_name in enumerate(df.columns):
                width = _estimate_column_width(df[col_name])
                should_wrap = width >= _WRAP_WIDTH_THRESHOLD
                wrap_flags.append(should_wrap)
                worksheet.set_column(col_idx, col_idx, width)
                worksheet.write(0, col_idx, str(col_name), header_fmt)

            worksheet.set_row(0, 32)

            for row_idx in range(n_rows):
                row_values = df.iloc[row_idx]
                for col_idx, col_name in enumerate(df.columns):
                    value = row_values[col_name]
                    if value is None or (isinstance(value, float) and pd.isna(value)):
                        value = ""
                    fmt = _fmt_for(row_idx, wrap_flags[col_idx])
                    worksheet.write(row_idx + 1, col_idx, value, fmt)

            worksheet.freeze_panes(1, max(0, min(freeze_first_col, n_cols)))
            worksheet.autofilter(0, 0, n_rows, n_cols - 1)

        for sheet_name, df in (extra_sheets_no_style or {}).items():
            safe_name = str(sheet_name)[:31] or "Аркуш"
            df = df if df is not None else pd.DataFrame()
            df.to_excel(writer, index=False, sheet_name=safe_name)

    return buffer.getvalue()

# ------------------------------------------------------------
# DOCX-вивантаження таблиць у альбомному форматі (DEMO 1.9)
# ------------------------------------------------------------

def dataframes_to_docx_landscape(
    sheets: dict,
    *,
    title: str = "Табличний звіт",
    subtitle: str = "",
) -> bytes | None:
    """Формує DOCX з кількома таблицями в альбомній орієнтації.

    Повертає bytes або None, якщо python-docx недоступний. Таблиці навмисно
    компактні: повторювана шапка у Word не гарантується, але файл придатний
    для друку й службового долучення до матеріалів.
    """
    try:
        from docx import Document
        from docx.enum.section import WD_ORIENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except Exception:
        return None

    import io
    import pandas as pd

    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.0)
    section.right_margin = Cm(1.0)

    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(8)

    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run(title)
    r.bold = True
    r.font.size = Pt(14)
    if subtitle:
        p = doc.add_paragraph(subtitle)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.size = Pt(8)

    for sheet_name, df in sheets.items():
        if df is None:
            continue
        try:
            frame = pd.DataFrame(df).fillna("")
        except Exception as exc:
            show_warning(
                f"Аркуш «{sheet_name}» не додано до Word-файлу.",
                exc,
                "Перетворення аркуша для Word-експорту",
            )
            continue
        doc.add_paragraph()
        ph = doc.add_paragraph(str(sheet_name))
        ph.runs[0].bold = True
        ph.runs[0].font.size = Pt(10)
        if frame.empty:
            doc.add_paragraph("Даних немає.")
            continue

        max_rows = min(len(frame), 250)
        max_cols = min(len(frame.columns), 12)
        frame = frame.iloc[:max_rows, :max_cols]

        table = doc.add_table(rows=1, cols=len(frame.columns))
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for i, col in enumerate(frame.columns):
            hdr[i].text = str(col)
            for paragraph in hdr[i].paragraphs:
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.bold = True
                    run.font.size = Pt(7)
            tc_pr = hdr[i]._tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:fill"), "434343")
            tc_pr.append(shd)

        for _, row in frame.iterrows():
            cells = table.add_row().cells
            for i, col in enumerate(frame.columns):
                value = str(row.get(col, ""))
                cells[i].text = value[:900]
                for paragraph in cells[i].paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(6.5)

        if len(pd.DataFrame(df)) > max_rows or len(pd.DataFrame(df).columns) > max_cols:
            doc.add_paragraph(
                f"Примітка: для друкованої версії показано перші {max_rows} рядків і {max_cols} колонок. "
                "Повний масив доступний в Excel-вивантаженні."
            )

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()

# ------------------------------------------------------------
# Головний Excel-експорт сторінки app.py
# ------------------------------------------------------------

_MATRIX_DARK_BLUE = "#032A63"
_MATRIX_DARK_ORANGE = "#C65911"
_MATRIX_GOAL_BLUE = "#5B9BD5"
_MATRIX_TASK_BLUE = "#D9EAF7"
_MATRIX_WHITE = "#FFFFFF"
_MATRIX_GREY = "#F2F2F2"
_MATRIX_TEXT = "#132238"


def _export_clean(value) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _quarter_roman(value) -> str:
    from core.periods import quarter_key
    return quarter_key(value)


def _latest_period_records(monitoring_df):
    """Індекс (code, year, quarter) -> найактуальніший запис."""
    import pandas as pd
    result = {}
    if monitoring_df is None or monitoring_df.empty:
        return result
    data = monitoring_df.copy()
    for col in ["strat_code", "year", "quarter", "submitted_at", "id"]:
        if col not in data.columns:
            data[col] = ""
    data["_submitted_sort"] = pd.to_datetime(data["submitted_at"], errors="coerce", utc=True)
    data["_id_sort"] = pd.to_numeric(data["id"], errors="coerce").fillna(-1)
    data = data.sort_values(["_submitted_sort", "_id_sort"], na_position="first")
    for _, row in data.iterrows():
        key = (
            _export_clean(row.get("strat_code")),
            _export_clean(row.get("year")),
            _quarter_roman(row.get("quarter")),
        )
        if all(key):
            result[key] = row
    return result


def _indicator_latest_value(indicator_df, row, year) -> str:
    """Останнє подане значення конкретного індикатора за роком."""
    import pandas as pd
    if indicator_df is None or indicator_df.empty:
        return ""
    data = indicator_df.copy()
    code = _export_clean(row.get("code"))
    indicator_name = _export_clean(row.get("indicator"))
    if "strat_code" not in data.columns:
        return ""
    data = data[data["strat_code"].astype(str).str.strip() == code]
    if "year" in data.columns:
        data = data[data["year"].astype(str).str.strip() == str(year)]
    if indicator_name and "indicator_name" in data.columns:
        exact = data[data["indicator_name"].astype(str).str.strip() == indicator_name]
        if not exact.empty:
            data = exact
    if data.empty:
        return ""
    if "submitted_at" not in data.columns:
        data["submitted_at"] = ""
    if "id" not in data.columns:
        data["id"] = ""
    data["_submitted_sort"] = pd.to_datetime(data["submitted_at"], errors="coerce", utc=True)
    data["_id_sort"] = pd.to_numeric(data["id"], errors="coerce").fillna(-1)
    data = data.sort_values(["_submitted_sort", "_id_sort"], ascending=[False, False])
    return _export_clean(data.iloc[0].get("numeric_value", ""))


def _indicator_matches_export_filters(row, selected_ssp_indices=None, selected_product_types=None, search_query="") -> bool:
    from core.text_utils import extract_ssp_index
    selected_ssp_indices = {str(x).strip() for x in (selected_ssp_indices or []) if str(x).strip()}
    if selected_ssp_indices:
        values = [row.get("resp_main", ""), row.get("resp_co_1", ""), row.get("resp_co_2", "")]
        indexes = {extract_ssp_index(v) for v in values if _export_clean(v)}
        if not (indexes & selected_ssp_indices):
            return False
    selected_product_types = {_export_clean(x) for x in (selected_product_types or []) if _export_clean(x)}
    if selected_product_types and _export_clean(row.get("product_type")) not in selected_product_types:
        return False
    query = _export_clean(search_query).lower()
    if query:
        haystack = " ".join(_export_clean(row.get(col, "")) for col in [
            "code", "name", "indicator", "product_type", "resp_main", "resp_co_1", "resp_co_2"
        ]).lower()
        if query not in haystack:
            return False
    return True


def _goal_number(code: str) -> str:
    import re
    match = re.search(r"\d+", _export_clean(code))
    return match.group(0) if match else _export_clean(code)


def _approval_route_and_current(record, logs=None) -> tuple[str, str, str]:
    """(координатор, накопичувальна схема, поточна ланка/стан погодження)."""
    from core import approval_schemes as schemes

    if record is None:
        return "", "", ""
    chain = schemes.parse_chain(record.get("approval_chain", ""))
    coordinator = ""
    for stage in chain:
        if _export_clean(stage.get("role")) == "admin":
            coordinator = _export_clean(stage.get("name")) or _export_clean(stage.get("email"))
            break

    approval = _export_clean(record.get("approval_status"))
    stage_idx = schemes.parse_stage(record.get("chain_stage"))
    scheme_text = schemes.approval_scheme_text(chain, stage_idx, approval, logs)

    if approval == schemes.APPROVED_STATUS:
        current = schemes.APPROVED_STATUS
    elif approval in schemes.ALL_RETURNED_STATUSES:
        current = approval
    elif approval == schemes.STATUS_WAITING_MANAGER_SELECTION:
        current = schemes.STATUS_WAITING_MANAGER_SELECTION
    else:
        stage = schemes.current_stage(chain, stage_idx)
        if stage:
            who = _export_clean(stage.get("name")) or _export_clean(stage.get("email"))
            label = _export_clean(stage.get("label"))
            current = f"{label} ({who})" if who else label
        else:
            current = approval
    return coordinator, scheme_text, current


def _load_export_logs():
    import pandas as pd
    try:
        from core.db import fetch_all
        return pd.DataFrame(fetch_all("monitoring_logs", "*", order=("changed_at", False)))
    except Exception:
        return pd.DataFrame()


def _request_export_logs(logs_df, request_id):
    """Журнал однієї заявки у хронологічному порядку для схеми експорту."""
    import pandas as pd

    if logs_df is None or logs_df.empty or request_id in (None, ""):
        return pd.DataFrame()
    if "request_id" not in logs_df.columns:
        return pd.DataFrame()
    try:
        rid = int(float(str(request_id)))
    except (TypeError, ValueError):
        return pd.DataFrame()
    mask = pd.to_numeric(logs_df["request_id"], errors="coerce") == rid
    data = logs_df[mask].copy()
    if data.empty or "changed_at" not in data.columns:
        return data
    data["_scheme_sort"] = pd.to_datetime(data["changed_at"], errors="coerce", utc=True)
    return data.sort_values("_scheme_sort", na_position="last")


def _approval_history(logs_df, request_id) -> str:
    import pandas as pd
    if logs_df is None or logs_df.empty or request_id in (None, "") or "request_id" not in logs_df.columns:
        return ""
    try:
        rid = int(float(str(request_id)))
        data = logs_df[pd.to_numeric(logs_df["request_id"], errors="coerce") == rid].copy()
    except Exception:
        return ""
    if data.empty:
        return ""
    if "changed_at" not in data.columns:
        data["changed_at"] = ""
    data["_sort"] = pd.to_datetime(data["changed_at"], errors="coerce", utc=True)
    data = data.sort_values("_sort", na_position="last")
    parts = []
    for _, row in data.iterrows():
        ts = pd.to_datetime(row.get("changed_at"), errors="coerce", utc=True)
        if pd.notna(ts):
            try:
                stamp = ts.tz_convert("Europe/Kyiv").strftime("%d.%m.%Y %H:%M")
            except Exception:
                stamp = str(ts)
        else:
            stamp = ""
        actor = _export_clean(row.get("actor_name")) or _export_clean(row.get("changed_by")) or _export_clean(row.get("actor_email"))
        action = _export_clean(row.get("action"))
        old_status = _export_clean(row.get("old_status"))
        new_status = _export_clean(row.get("new_status"))
        transition = " → ".join(x for x in [old_status, new_status] if x)
        comment = _export_clean(row.get("admin_comment"))
        item = " · ".join(x for x in [stamp, actor, action, transition, comment] if x)
        if item:
            parts.append(item)
    return "\n".join(parts)


def _write_matrix_sheet(
    workbook,
    strat_df,
    filtered_measures,
    monitoring_df,
    indicator_monitoring_df,
    selected_years,
    selected_quarters,
    selected_ssp_indices,
    selected_product_types,
    search_query,
):
    import pandas as pd
    from core.period_locks import is_period_locked
    from core.text_utils import strip_leading_code

    ws = workbook.add_worksheet("Матриця стратег. результатів")

    title_fmt = workbook.add_format({"bold": True, "font_color": _MATRIX_DARK_BLUE, "font_size": 16, "align": "left", "valign": "vcenter"})
    header_blue = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": _MATRIX_DARK_BLUE, "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1, "border_color": "#FFFFFF"})
    header_orange = workbook.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": _MATRIX_DARK_ORANGE, "align": "center", "valign": "vcenter", "text_wrap": True, "border": 1, "border_color": "#FFFFFF"})
    number_fmt = workbook.add_format({"bold": True, "font_color": _MATRIX_TEXT, "align": "center", "valign": "vcenter", "border": 1, "border_color": _BORDER_COLOR})
    goal_fmt = workbook.add_format({"bg_color": _MATRIX_GOAL_BLUE, "font_color": "#FFFFFF", "bold": True, "valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR})
    task_fmt = workbook.add_format({"bg_color": _MATRIX_TASK_BLUE, "font_color": _MATRIX_TEXT, "bold": True, "valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR})
    measure_white = workbook.add_format({"bg_color": _MATRIX_WHITE, "font_color": _MATRIX_TEXT, "valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR})
    measure_grey = workbook.add_format({"bg_color": _MATRIX_GREY, "font_color": _MATRIX_TEXT, "valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR})

    selected_years = [int(y) for y in (selected_years or [])]
    selected_quarters = [_quarter_roman(q) for q in (selected_quarters or []) if _quarter_roman(q)]
    q_label = {"I": "Q1", "II": "Q2", "III": "Q3", "IV": "Q4"}

    # Структура колонок. A — службова порожня; нумерація починається з B=1.
    columns = [
        {"key": "_a", "kind": "blue"},
        {"key": "_group", "kind": "blue"},
        {"key": "_code", "kind": "blue"},
        {"key": "name", "kind": "blue", "single": "Стратегічні цілі, завдання та заходи до них"},
        {"key": "product_type", "kind": "blue", "single": "Тип продукту"},
        {"key": "indicator", "kind": "blue", "single": "Індикатор"},
        {"key": "unit", "kind": "blue", "single": "Одиниці виміру"},
        {"key": "base_2021", "kind": "orange", "year": "2021", "sub": "базовий рівень (факт)"},
        {"key": "fact_2024", "kind": "orange", "year": "2024", "sub": "звіт"},
        {"key": "fact_2025", "kind": "orange", "year": "2025", "sub": "факт"},
    ]
    for year in [2026, 2027, 2028]:
        columns.append({"key": f"target_{year}", "kind": "orange", "year": str(year), "sub": "цільовий орієнтир для заходів на рік"})
        if year in selected_years:
            for quarter in selected_quarters:
                columns.append({"key": f"q_{year}_{quarter}", "kind": "orange", "single": f"{year} {q_label.get(quarter, quarter)}", "quarter": (year, quarter)})

    # Роки 2029–2033 не мають окремих планових колонок у затвердженій матриці;
    # їхні обрані квартальні зрізи ставимо після планового блоку 2028.
    for year in [y for y in selected_years if y in {2029, 2030, 2031, 2032, 2033}]:
        for quarter in selected_quarters:
            columns.append({"key": f"q_{year}_{quarter}", "kind": "orange", "single": f"{year} {q_label.get(quarter, quarter)}", "quarter": (year, quarter)})

    columns.append({"key": "strategic_target_2028", "kind": "orange", "single": "Проміжний цільовий орієнтир на кінець 2028 року"})
    columns.append({"key": "strategic_target_2034", "kind": "orange", "single": "Цільовий орієнтир на кінець 2034 року для цілей і завдань (відповідає цілі, визначеній в НЕС-2030, ЦСР-2030 для показників, де це зазначено. Ціль перенесена на 2034 рік через «втрату» 4-х років — 2022–2025 внаслідок повномасштабної війни. Інші індикативні значення мають встановлюватися такими, що є кількісно узгодженими з цілями НЕС і ЦСР)"})
    if 2034 in selected_years:
        for quarter in selected_quarters:
            columns.append({"key": f"q_2034_{quarter}", "kind": "orange", "single": f"2034 {q_label.get(quarter, quarter)}", "quarter": (2034, quarter)})

    # Службові маркери для багаторівневої шапки.
    source_global_idx = len(columns)
    columns += [
        {"key": "source_global", "kind": "blue"},
        {"key": "source_national", "kind": "blue"},
    ]
    resp_idx = len(columns)
    columns += [
        {"key": "resp_main", "kind": "blue"},
        {"key": "resp_co", "kind": "blue"},
        {"key": "deputy_minister_raw", "kind": "blue", "single": "Заступник Міністра"},
        {"key": "measure_period_years", "kind": "blue", "single": "Період дії заходу в межах планового періоду, років"},
        {"key": "measure_start_date", "kind": "blue", "single": "Початкова дата"},
        {"key": "measure_end_date", "kind": "blue", "single": "Кінцева дата"},
    ]
    finance_idx = len(columns)
    columns += [
        {"key": "budget_kpkvk", "kind": "blue"},
        {"key": "budget_2026_approved", "kind": "blue"},
        {"key": "budget_2027_forecast", "kind": "blue"},
        {"key": "budget_2028_forecast", "kind": "blue"},
        {"key": "other_source", "kind": "blue"},
        {"key": "other_2026_plan", "kind": "blue"},
        {"key": "other_2027_forecast", "kind": "blue"},
        {"key": "other_2028_forecast", "kind": "blue"},
    ]

    last_col = len(columns) - 1
    ws.merge_range(0, 0, 0, 3, "Матриця стратегічних результатів", title_fmt)
    ws.set_row(0, 24)
    ws.set_row(1, 8)

    # Рядки 3–5 (xlsxwriter zero-based 2–4).
    for idx, col in enumerate(columns):
        fmt = header_orange if col.get("kind") == "orange" else header_blue
        if col.get("single"):
            ws.merge_range(2, idx, 4, idx, col["single"], fmt)
        elif col.get("year"):
            ws.write(2, idx, col["year"], fmt)
            ws.merge_range(3, idx, 4, idx, col["sub"], fmt)
        elif idx < 3:
            ws.merge_range(2, idx, 4, idx, "", fmt)

    source_title = "Джерело даних (для індикаторів)/Підстава для включення (для заходів)"
    ws.merge_range(2, source_global_idx, 3, source_global_idx, source_title, header_blue)
    ws.write(4, source_global_idx, "Глобальний рівень", header_blue)
    ws.merge_range(2, source_global_idx + 1, 3, source_global_idx + 1, source_title, header_blue)
    ws.write(4, source_global_idx + 1, "Національний рівень", header_blue)

    ws.merge_range(2, resp_idx, 3, resp_idx + 1, "Відповідальні самостійні структурні підрозділи", header_blue)
    ws.write(4, resp_idx, "Головний виконавець", header_blue)
    ws.write(4, resp_idx + 1, "Співвиконавець", header_blue)

    ws.merge_range(2, finance_idx, 2, finance_idx + 7, "Фінансування", header_blue)
    ws.merge_range(3, finance_idx, 3, finance_idx + 3, "Державний бюджет України", header_blue)
    ws.merge_range(3, finance_idx + 4, 3, finance_idx + 7, "Інші джерела", header_blue)
    finance_headers = [
        "КПКВК", "2026 затверджено, млрд грн", "2027 прогноз, млрд грн", "2028 прогноз, млрд грн",
        "Джерело (МТД, кошти партнерів, інші небюджетні джерела)", "2026 план", "2027 прогноз", "2028 прогноз",
    ]
    for offset, label in enumerate(finance_headers):
        ws.write(4, finance_idx + offset, label, header_blue)

    # Нумерація рядка 6: B=1, A порожня.
    ws.write(5, 0, "", number_fmt)
    for idx in range(1, last_col + 1):
        ws.write(5, idx, idx, number_fmt)

    ws.freeze_panes(6, 0)
    ws.set_row(2, 42)
    ws.set_row(3, 42)
    ws.set_row(4, 58)

    # Ширини.
    widths = {0: 3, 1: 18, 2: 20, 3: 48, 4: 22, 5: 42, 6: 18}
    for idx in range(len(columns)):
        width = widths.get(idx, 18)
        key = columns[idx]["key"]
        if key.startswith("q_"):
            width = 14
        elif key in {"source_global", "source_national"}:
            width = 34
        elif key in {"resp_main", "resp_co", "deputy_minister_raw"}:
            width = 24
        elif key in {"other_source"}:
            width = 34
        ws.set_column(idx, idx, width)

    record_index = _latest_period_records(monitoring_df)

    measures = filtered_measures.copy() if filtered_measures is not None else pd.DataFrame()
    if measures.empty:
        return ws
    goal_codes = list(dict.fromkeys(measures["parent_goal_code"].astype(str).str.strip().tolist()))
    task_codes = list(dict.fromkeys(measures["parent_task_code"].astype(str).str.strip().tolist()))
    goals = strat_df[(strat_df["object_type"] == "goal") & strat_df["code"].astype(str).str.strip().isin(goal_codes)].copy()
    tasks = strat_df[(strat_df["object_type"] == "task") & strat_df["code"].astype(str).str.strip().isin(task_codes)].copy()

    def indicator_rows_for(kind: str, code: str):
        if kind == "goal":
            rows = strat_df[
                (strat_df["object_type"].isin(["goal", "goal_indicator"]))
                & (strat_df["parent_goal_code"].astype(str).str.strip().eq(code) | strat_df["code"].astype(str).str.strip().eq(code))
                & (strat_df["parent_task_code"].astype(str).str.strip() == "")
            ].copy()
        else:
            rows = strat_df[
                (strat_df["object_type"].isin(["task", "task_indicator"]))
                & (strat_df["parent_task_code"].astype(str).str.strip().eq(code) | strat_df["code"].astype(str).str.strip().eq(code))
            ].copy()
        return [
            row for _, row in rows.iterrows()
            if _export_clean(row.get("indicator"))
            and _indicator_matches_export_filters(
                row, selected_ssp_indices, selected_product_types, search_query
            )
        ]

    def row_values(source, row_type: str, group="", code_value=""):
        values = {col["key"]: "" for col in columns}
        values["_group"] = group
        values["_code"] = code_value
        if source is not None:
            for col in columns:
                key = col["key"]
                if key == "resp_co":
                    values[key] = "; ".join(x for x in [_export_clean(source.get("resp_co_1")), _export_clean(source.get("resp_co_2"))] if x)
                elif key.startswith("q_"):
                    year, quarter = col["quarter"]
                    if row_type == "measure":
                        record = record_index.get((_export_clean(source.get("code")), str(year), quarter))
                        actual = _export_clean(record.get("numeric_value")) if record is not None else ""
                        if is_period_locked(year, quarter) and not actual:
                            actual = "Не настав час"
                        values[key] = actual
                elif key in source:
                    values[key] = _export_clean(source.get(key))
            if row_type == "indicator":
                for key, year in [("base_2021", 2021), ("fact_2024", 2024), ("fact_2025", 2025), ("target_2026", 2026), ("target_2027", 2027), ("target_2028", 2028)]:
                    current = _export_clean(values.get(key))
                    if current.lower() in {"x", "х"}:
                        latest = _indicator_latest_value(indicator_monitoring_df, source, year)
                        if latest:
                            values[key] = latest
        if row_type == "indicator":
            values["name"] = ""
        return [values[col["key"]] for col in columns]

    out_row = 6
    zebra = 0
    for _, goal in goals.iterrows():
        goal_code = _export_clean(goal.get("code"))
        goal_measures = measures[measures["parent_goal_code"].astype(str).str.strip() == goal_code]
        if goal_measures.empty:
            continue
        goal_name = strip_leading_code(goal.get("name", ""), goal_code)
        values = row_values(None, "goal", f"Стратегічна ціль {_goal_number(goal_code)}", goal_name)
        for col_idx, value in enumerate(values):
            ws.write(out_row, col_idx, value, goal_fmt)
        out_row += 1
        for indicator_row in indicator_rows_for("goal", goal_code):
            values = row_values(indicator_row, "indicator")
            for col_idx, value in enumerate(values):
                ws.write(out_row, col_idx, value, goal_fmt)
            out_row += 1

        goal_task_codes = list(dict.fromkeys(goal_measures["parent_task_code"].astype(str).str.strip().tolist()))
        goal_tasks = tasks[tasks["code"].astype(str).str.strip().isin(goal_task_codes)]
        for _, task in goal_tasks.iterrows():
            task_code = _export_clean(task.get("code"))
            task_name = strip_leading_code(task.get("name", ""), task_code)
            values = row_values(None, "task", "Завдання:", "")
            # За ТЗ назва завдання — у колонці D.
            values[3] = task_name
            for col_idx, value in enumerate(values):
                ws.write(out_row, col_idx, value, task_fmt)
            out_row += 1
            for indicator_row in indicator_rows_for("task", task_code):
                values = row_values(indicator_row, "indicator")
                for col_idx, value in enumerate(values):
                    ws.write(out_row, col_idx, value, task_fmt)
                out_row += 1

            task_measures = goal_measures[goal_measures["parent_task_code"].astype(str).str.strip() == task_code]
            for measure_idx, (_, measure) in enumerate(task_measures.iterrows()):
                code = _export_clean(measure.get("code"))
                values = row_values(measure, "measure", "Заходи:" if measure_idx == 0 else "", code)
                values[3] = strip_leading_code(measure.get("name", ""), code)
                fmt = measure_grey if zebra % 2 else measure_white
                zebra += 1
                for col_idx, value in enumerate(values):
                    ws.write(out_row, col_idx, value, fmt)
                out_row += 1

    return ws


def _build_detailed_export_df(filtered_measures, monitoring_df, selected_years, selected_quarters, manual_closeouts):
    import pandas as pd
    from core.period_locks import is_period_locked
    from core.text_utils import strip_leading_code

    q_label = {"I": "Q1", "II": "Q2", "III": "Q3", "IV": "Q4"}
    records = _latest_period_records(monitoring_df)
    logs_df = _load_export_logs()
    manual_closeouts = set(manual_closeouts or set())
    rows = []
    for _, measure in filtered_measures.iterrows():
        code = _export_clean(measure.get("code"))
        row = {
            "Код": code,
            "Захід": strip_leading_code(measure.get("name", ""), code),
            "Тип продукту": _export_clean(measure.get("product_type")),
            "Індикатор": _export_clean(measure.get("indicator")),
            "Одиниці виміру": _export_clean(measure.get("unit")),
            "Головний виконавець": _export_clean(measure.get("resp_main")),
            "Співвиконавець": "; ".join(x for x in [_export_clean(measure.get("resp_co_1")), _export_clean(measure.get("resp_co_2"))] if x),
        }
        for year in selected_years or []:
            for quarter in selected_quarters or []:
                q = _quarter_roman(quarter)
                prefix = f"{year} {q_label.get(q, q)}"
                record = records.get((code, str(year), q))
                locked = is_period_locked(year, q)
                actual = _export_clean(record.get("numeric_value")) if record is not None else ""
                if locked and not actual:
                    actual = "—"
                row[prefix] = actual
                if locked:
                    status = "Не настав час"
                elif record is not None:
                    status = _export_clean(record.get("status"))
                elif (code, str(year), q) in manual_closeouts:
                    status = "Виконано"
                else:
                    status = ""
                record_logs = (
                    _request_export_logs(logs_df, record.get("id"))
                    if record is not None else None
                )
                coordinator, scheme_history, current = _approval_route_and_current(
                    record,
                    record_logs,
                )
                row[f"{prefix} — Статус заходу"] = status
                row[f"{prefix} — Відповідальна особа від ССП"] = _export_clean(record.get("responsible_person")) if record is not None else ""
                row[f"{prefix} — Координатор"] = coordinator
                row[f"{prefix} — Опис прогресу виконання"] = _export_clean(record.get("progress_text")) if record is not None else ""
                row[f"{prefix} — Ризики/проблеми/відхилення"] = _export_clean(record.get("risks")) if record is not None else ""
                row[f"{prefix} — Посилання на НПА"] = _export_clean(record.get("npa_link")) if record is not None else ""
                row[f"{prefix} — Діюча схема погодження"] = scheme_history
                row[f"{prefix} — Поточний статус погодження"] = current
        rows.append(row)
    return pd.DataFrame(rows)


def build_main_monitoring_export(
    *,
    strat_df,
    filtered_measures,
    monitoring_df,
    indicator_monitoring_df,
    selected_years,
    selected_quarters,
    selected_ssp_indices=None,
    selected_product_types=None,
    search_query="",
    manual_closeouts=None,
) -> bytes:
    """Єдиний двовкладковий Excel головної сторінки за застосованими фільтрами."""
    import io
    import pandas as pd

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        matrix_ws = _write_matrix_sheet(
            workbook,
            strat_df,
            filtered_measures,
            monitoring_df,
            indicator_monitoring_df,
            selected_years,
            selected_quarters,
            selected_ssp_indices,
            selected_product_types,
            search_query,
        )
        writer.sheets["Матриця стратег. результатів"] = matrix_ws

        detail_df = _build_detailed_export_df(
            filtered_measures,
            monitoring_df,
            selected_years,
            selected_quarters,
            manual_closeouts,
        )
        sheet_name = "Детальні моніторингові дані"
        ws = workbook.add_worksheet(sheet_name)
        writer.sheets[sheet_name] = ws
        header_fmt = workbook.add_format({
            "bold": True, "font_color": _HEADER_FG, "bg_color": _HEADER_BG,
            "align": "center", "valign": "vcenter", "text_wrap": True,
            "border": 1, "border_color": "#FFFFFF",
        })
        cell_fmt = workbook.add_format({"valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR})
        band_fmt = workbook.add_format({"valign": "top", "text_wrap": True, "border": 1, "border_color": _BORDER_COLOR, "bg_color": _BAND_BG})
        for col_idx, col_name in enumerate(detail_df.columns):
            ws.write(0, col_idx, col_name, header_fmt)
            width = min(max(len(str(col_name)) + 2, 14), 42)
            if "Опис прогресу" in str(col_name) or "Ризики" in str(col_name) or "Діюча схема" in str(col_name):
                width = 45
            ws.set_column(col_idx, col_idx, width)
        for row_idx in range(len(detail_df)):
            fmt = band_fmt if row_idx % 2 else cell_fmt
            for col_idx, col_name in enumerate(detail_df.columns):
                value = detail_df.iloc[row_idx][col_name]
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    value = ""
                ws.write(row_idx + 1, col_idx, value, fmt)
        if len(detail_df.columns):
            ws.freeze_panes(1, 2)
            ws.autofilter(0, 0, len(detail_df), len(detail_df.columns) - 1)
            ws.set_row(0, 42)

    return buffer.getvalue()
