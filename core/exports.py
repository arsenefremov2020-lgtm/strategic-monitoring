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
    """Реєструє кириличні шрифти DejaVu; повертає (regular, bold) або None.

    Порядок пошуку: 1) шрифти, ПОКЛАДЕНІ В РЕПОЗИТОРІЙ (assets/fonts) —
    гарантують однаковий рендер на Streamlit Cloud; 2) системні DejaVu.
    Без кириличного шрифту reportlab малює «квадрати» замість українських
    літер — саме тому бандл у репозиторії обов'язковий.
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        _candidates = [
            (Path("assets/fonts/DejaVuSans.ttf"),
             Path("assets/fonts/DejaVuSans-Bold.ttf")),
            (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
             Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        ]
        for regular_path, bold_path in _candidates:
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
# візуальний стиль, що й у "Під моніторинг СП.xlsx" — колір #434343),
# закріplena шапка, автофільтр, розумна ширина колонок за вмістом,
# перенос тексту в довгих колонках, тонкі межі й легке "зебра"-заливання
# рядків для зручного читання великих вивантажень.

_HEADER_BG = "#434343"
_HEADER_FG = "#FFFFFF"
_BORDER_COLOR = "#D1D5DB"
_BAND_BG = "#F8FAFC"

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
        except Exception:
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
