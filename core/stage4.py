"""Helpers for DEMO 2.0 Stage 4: card links, PDFs and workflow analytics."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import pandas as pd
import streamlit as st

from core import approval_schemes as schemes
from core.timeutils import KYIV_TZ, now_kyiv

WAITING_STATUS_LABELS = {
    schemes.STATUS_COORDINATOR_REVIEW: "Координатор",
    schemes.STATUS_WAITING_MANAGER_SELECTION: "Вибір керівника подавачем",
    schemes.STATUS_SUPERADMIN_REVIEW: "Супер-адмін",
    schemes.STATUS_MANAGER_REVIEW: "Керівник ССП / заступник",
}
CARD_TARGET_SESSION_KEY = "stage4_card_target"


# ---------------------------------------------------------------------------
# Common formatting
# ---------------------------------------------------------------------------

def clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "nat"} else text


def _series(frame: pd.DataFrame, column: str, default: Any = "") -> pd.Series:
    """Return a column-sized Series even when the source column is absent."""
    if column in frame.columns:
        return frame[column]
    return pd.Series([default] * len(frame), index=frame.index, dtype="object")


def quarter_to_roman(value: Any) -> str:
    text = clean(value).upper().replace("КВАРТАЛ", "").replace("КВ.", "").strip()
    mapping = {"1": "I", "2": "II", "3": "III", "4": "IV", "I": "I", "II": "II", "III": "III", "IV": "IV"}
    return mapping.get(text, text)


def kyiv_now() -> datetime:
    return now_kyiv()


def format_kyiv_datetime(value: Any, fallback: str = "—") -> str:
    if value is None or clean(value) == "":
        return fallback
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return clean(value) or fallback
    return ts.tz_convert("Europe/Kyiv").strftime("%d.%m.%Y %H:%M")


def format_date(value: Any, fallback: str = "—") -> str:
    if value is None or clean(value) == "":
        return fallback
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return clean(value) or fallback
    return ts.strftime("%d.%m.%Y")


def data_read_caption(read_at: datetime | None = None) -> str:
    read_at = read_at or kyiv_now()
    if read_at.tzinfo is None:
        read_at = read_at.replace(tzinfo=KYIV_TZ)
    return f"Дані станом на {read_at.astimezone(KYIV_TZ).strftime('%d.%m.%Y %H:%M')}"


# ---------------------------------------------------------------------------
# Direct links to measure cards
# ---------------------------------------------------------------------------

def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return clean(value)


def get_card_target() -> dict[str, str]:
    """Read the card target from URL, falling back to same-session navigation."""
    target = {
        "code": _query_value("code"),
        "year": _query_value("year"),
        "quarter": quarter_to_roman(_query_value("quarter")),
    }
    if target["code"]:
        st.session_state[CARD_TARGET_SESSION_KEY] = target.copy()
        return target
    fallback = st.session_state.get(CARD_TARGET_SESSION_KEY, {}) or {}
    return {
        "code": clean(fallback.get("code")),
        "year": clean(fallback.get("year")),
        "quarter": quarter_to_roman(fallback.get("quarter")),
    }


def set_card_target(code: Any, year: Any, quarter: Any) -> None:
    target = {
        "code": clean(code),
        "year": clean(year),
        "quarter": quarter_to_roman(quarter),
    }
    st.session_state[CARD_TARGET_SESSION_KEY] = target
    try:
        st.query_params.clear()
        st.query_params["code"] = target["code"]
        st.query_params["year"] = target["year"]
        st.query_params["quarter"] = target["quarter"]
    except Exception:
        pass


def switch_to_card(code: Any, year: Any, quarter: Any) -> None:
    set_card_target(code, year, quarter)
    st.switch_page("pages/4_Картка_заходу.py")


def card_relative_url(code: Any, year: Any, quarter: Any) -> str:
    params = (
        f"code={quote(clean(code))}&year={quote(clean(year))}"
        f"&quarter={quote(quarter_to_roman(quarter))}"
    )
    return f"./Картка_заходу?{params}"


def render_copy_card_link(code: Any, year: Any, quarter: Any, *, key: str) -> None:
    """Render a browser-side copy button that builds an absolute URL at runtime."""
    import streamlit.components.v1 as components

    code_js = json.dumps(clean(code), ensure_ascii=False)
    year_js = json.dumps(clean(year), ensure_ascii=False)
    quarter_js = json.dumps(quarter_to_roman(quarter), ensure_ascii=False)
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
    components.html(
        f"""
        <style>
        .copy-wrap {{ display:flex; align-items:center; gap:10px; font-family:Arial,sans-serif; }}
        .copy-btn {{ width:100%; border:1px solid #93c5fd; border-radius:9px; padding:9px 14px;
          background:#eff6ff; color:#1d4ed8; font-weight:700; cursor:pointer; }}
        .copy-btn:hover {{ background:#dbeafe; }}
        .copy-result {{ min-width:145px; font-size:12px; font-weight:700; color:#166534; }}
        </style>
        <div class="copy-wrap">
          <button class="copy-btn" id="copy-{safe_key}">🔗 Скопіювати посилання на цю картку</button>
          <span class="copy-result" id="result-{safe_key}"></span>
        </div>
        <script>
        const button = document.getElementById('copy-{safe_key}');
        const result = document.getElementById('result-{safe_key}');
        button.addEventListener('click', async () => {{
          let sourceUrl = document.referrer || window.location.href;
          try {{
            sourceUrl = window.parent.location.href || sourceUrl;
          }} catch (error) {{
            // У деяких конфігураціях компонент працює в ізольованому iframe.
          }}
          const url = new URL(sourceUrl);
          url.search = '';
          url.searchParams.set('code', {code_js});
          url.searchParams.set('year', {year_js});
          url.searchParams.set('quarter', {quarter_js});
          const text = url.toString();

          const fallbackCopy = () => {{
            const area = document.createElement('textarea');
            area.value = text;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            const copied = document.execCommand('copy');
            area.remove();
            if (!copied) throw new Error('copy command failed');
          }};

          try {{
            const clipboard = navigator.clipboard || window.parent?.navigator?.clipboard;
            if (clipboard && clipboard.writeText) {{
              try {{
                await clipboard.writeText(text);
              }} catch (clipboardError) {{
                fallbackCopy();
              }}
            }} else {{
              fallbackCopy();
            }}
            result.style.color = '#166534';
            result.textContent = 'Посилання скопійовано';
          }} catch (error) {{
            result.style.color = '#991b1b';
            result.textContent = 'Не вдалося скопіювати';
          }}
        }});
        </script>
        """,
        height=52,
    )


def render_measure_rows_with_card_links(frame: pd.DataFrame, *, key_prefix: str) -> None:
    """Human list with one deterministic card-navigation button per row."""
    if frame is None or frame.empty:
        st.info("У цій категорії заходів немає.")
        return

    data = frame.copy().reset_index(drop=True)
    st.caption(f"Рядків у деталізації: {len(data)}")
    header = st.columns([1.05, 4.0, 2.0, 1.7, 1.25])
    for col, label in zip(header, ["Код", "Захід", "ССП", "Статус", "Картка"]):
        col.markdown(f"**{label}**")

    for idx, row in data.iterrows():
        code = clean(row.get("code") or row.get("strat_code"))
        year = clean(row.get("report_year") or row.get("year"))
        quarter = quarter_to_roman(row.get("report_quarter") or row.get("quarter"))
        columns = st.columns([1.05, 4.0, 2.0, 1.7, 1.25])
        columns[0].write(code or "—")
        columns[1].write(clean(row.get("name") or row.get("object_name")) or "—")
        columns[2].write(clean(row.get("department") or row.get("ssp_department")) or "—")
        columns[3].write(clean(row.get("status_display") or row.get("status")) or "—")
        if columns[4].button("Відкрити", key=f"{key_prefix}_{idx}_{code}_{year}_{quarter}", use_container_width=True):
            switch_to_card(code, year, quarter)


# ---------------------------------------------------------------------------
# Human history / version comparison
# ---------------------------------------------------------------------------

VERSION_FIELDS: list[tuple[str, str, str]] = [
    ("status", "Статус виконання", "text"),
    ("approval_status", "Статус погодження", "text"),
    ("numeric_value", "Фактичне числове значення", "text"),
    ("value_text", "Фактичне текстове значення", "text"),
    ("progress_text", "Опис прогресу", "text"),
    ("risks", "Ризики / проблеми / відхилення", "text"),
    ("npa_link", "Посилання на НПА", "text"),
    ("responsible_person", "Відповідальна особа", "text"),
    ("phone", "Телефон", "text"),
    ("email", "Email", "text"),
    ("approval_chain", "Маршрут погодження", "chain"),
    ("chain_stage", "Поточна ланка маршруту", "text"),
    ("admin_comment", "Коментар", "text"),
    ("submitted_at", "Дата подання", "datetime"),
    ("as_of_date", "Станом на дату", "date"),
]


def _format_chain(value: Any) -> str:
    text = clean(value)
    if not text:
        return "—"
    try:
        chain = json.loads(text) if isinstance(value, str) else value
        if isinstance(chain, list):
            labels = [clean(x.get("label") or x.get("role")) for x in chain if isinstance(x, dict)]
            return " → ".join(x for x in labels if x) or "—"
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return text


def _format_version_value(value: Any, kind: str) -> str:
    if kind == "datetime":
        return format_kyiv_datetime(value)
    if kind == "date":
        return format_date(value)
    if kind == "chain":
        return _format_chain(value)
    return clean(value) or "—"


def version_option_label(row: pd.Series) -> str:
    return (
        f"Версія {clean(row.get('version_number')) or '—'} · "
        f"{format_kyiv_datetime(row.get('created_at'))} · "
        f"{clean(row.get('created_by')) or 'система'}"
    )


def version_differences(before: pd.Series, after: pd.Series) -> pd.DataFrame:
    """Return only user-visible fields that differ between two snapshots."""
    rows: list[dict[str, str]] = []
    for field, label, kind in VERSION_FIELDS:
        old = _format_version_value(before.get(field), kind)
        new = _format_version_value(after.get(field), kind)
        if old != new:
            rows.append({"Поле": label, "Було": old, "Стало": new})
    return pd.DataFrame(rows, columns=["Поле", "Було", "Стало"])


def render_version_comparison(versions_df: pd.DataFrame, *, key_prefix: str) -> None:
    """Compare two snapshots and show only fields whose visible values differ."""
    if versions_df is None or versions_df.empty or len(versions_df) < 2:
        st.info("Для порівняння потрібні щонайменше дві версії заявки.")
        return

    versions = versions_df.copy()
    versions["_version_sort"] = pd.to_numeric(versions.get("version_number"), errors="coerce")
    versions = versions.sort_values(["_version_sort", "created_at"], na_position="last").reset_index(drop=True)
    labels = {idx: version_option_label(row) for idx, row in versions.iterrows()}
    default_before = max(len(versions) - 2, 0)
    default_after = len(versions) - 1

    c1, c2 = st.columns(2)
    with c1:
        before_idx = st.selectbox(
            "Було — оберіть версію",
            options=list(labels),
            index=default_before,
            format_func=lambda idx: labels[idx],
            key=f"{key_prefix}_before",
        )
    with c2:
        after_idx = st.selectbox(
            "Стало — оберіть версію",
            options=list(labels),
            index=default_after,
            format_func=lambda idx: labels[idx],
            key=f"{key_prefix}_after",
        )

    before = versions.loc[int(before_idx)]
    after = versions.loc[int(after_idx)]
    comparison = version_differences(before, after)

    if comparison.empty:
        st.success("У вибраних версіях немає відмінностей у користувацьких полях.")
        return

    styled = comparison.style.set_properties(
        subset=["Було"], **{"background-color": "#fff7ed", "white-space": "pre-wrap"}
    ).set_properties(
        subset=["Стало"], **{"background-color": "#eff6ff", "white-space": "pre-wrap"}
    ).set_properties(subset=["Поле"], **{"font-weight": "700"})
    st.dataframe(styled, use_container_width=True, hide_index=True)


def human_versions_table(versions_df: pd.DataFrame) -> pd.DataFrame:
    if versions_df is None or versions_df.empty:
        return pd.DataFrame()
    show = versions_df.copy()
    show["Версія"] = _series(show, "version_number").apply(clean)
    show["Дата створення"] = _series(show, "created_at").apply(format_kyiv_datetime)
    show["Ким створено"] = _series(show, "created_by").apply(lambda x: clean(x) or "система")
    show["Статус погодження"] = _series(show, "approval_status").apply(lambda x: clean(x) or "—")
    show["Статус виконання"] = _series(show, "status").apply(lambda x: clean(x) or "—")
    numeric = _series(show, "numeric_value").apply(clean)
    textual = _series(show, "value_text").apply(clean)
    show["Фактичне значення"] = [n or t or "—" for n, t in zip(numeric, textual)]
    show["Опис прогресу"] = _series(show, "progress_text").apply(lambda x: clean(x) or "—")
    show["Ризики / проблеми"] = _series(show, "risks").apply(lambda x: clean(x) or "—")
    return show[[
        "Версія", "Дата створення", "Ким створено", "Статус погодження",
        "Статус виконання", "Фактичне значення", "Опис прогресу", "Ризики / проблеми",
    ]]


def style_status_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.io.formats.style.Styler:
    def colour(value: Any) -> str:
        text = clean(value)
        if text in {"Погоджено", "Виконано"}:
            return "background-color:#dcfce7;color:#166534;font-weight:700"
        if "Повернуто" in text or text == "Не виконано":
            return "background-color:#fee2e2;color:#991b1b;font-weight:700"
        if "Очікує" in text or text in {"Частково виконано", "Виконується"}:
            return "background-color:#fef9c3;color:#854d0e;font-weight:700"
        if text in {"Не настав час", "Втратило актуальність", "Відкликано"}:
            return "background-color:#f1f5f9;color:#475569;font-weight:700"
        return ""

    styler = frame.style
    for column in columns:
        if column in frame.columns:
            styler = styler.map(colour, subset=[column])
    return styler


# ---------------------------------------------------------------------------
# PDF measure card
# ---------------------------------------------------------------------------

def build_measure_card_pdf(
    *,
    measure: dict[str, Any],
    goal_name: str,
    task_name: str,
    requests_df: pd.DataFrame,
    logs_df: pd.DataFrame,
    focus_year: Any,
    focus_quarter: Any,
    closed_periods: Iterable[str] | None = None,
) -> bytes:
    """Build a printable A4 card PDF with embedded DejaVu fonts."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    regular = Path("assets/fonts/DejaVuSans.ttf")
    bold = Path("assets/fonts/DejaVuSans-Bold.ttf")
    if not regular.exists():
        raise FileNotFoundError("Не знайдено assets/fonts/DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont("Stage4DejaVu", str(regular)))
    pdfmetrics.registerFont(TTFont("Stage4DejaVu-Bold", str(bold if bold.exists() else regular)))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Картка заходу {clean(measure.get('code'))}",
        author="Система моніторингу стратегічного плану",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CardTitle", parent=styles["Title"], fontName="Stage4DejaVu-Bold",
        fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "CardH2", parent=styles["Heading2"], fontName="Stage4DejaVu-Bold",
        fontSize=11, leading=14, textColor=colors.HexColor("#0f172a"), spaceBefore=8, spaceAfter=5,
    )
    body = ParagraphStyle(
        "CardBody", parent=styles["BodyText"], fontName="Stage4DejaVu",
        fontSize=8.5, leading=11, alignment=TA_LEFT, wordWrap="CJK",
    )
    small = ParagraphStyle(
        "CardSmall", parent=body, fontSize=7.4, leading=9.3,
    )
    small_bold = ParagraphStyle(
        "CardSmallBold", parent=small, fontName="Stage4DejaVu-Bold",
    )

    def p(value: Any, style: ParagraphStyle = body) -> Paragraph:
        return Paragraph(escape(clean(value) or "—").replace("\n", "<br/>"), style)

    story: list[Any] = [
        Paragraph("КАРТКА СТРАТЕГІЧНОГО ЗАХОДУ", title_style),
        Paragraph(
            f"Код {escape(clean(measure.get('code')))} · фокус: "
            f"{escape(quarter_to_roman(focus_quarter))} квартал {escape(clean(focus_year))} року · ТЕСТОВИЙ РЕЖИМ",
            ParagraphStyle("Subtitle", parent=small, alignment=TA_CENTER, textColor=colors.HexColor("#475569")),
        ),
        Spacer(1, 5 * mm),
        Paragraph("Паспортні дані", h2),
    ]

    passport_rows = [
        [p("Захід", small_bold), p(measure.get("name"))],
        [p("Стратегічна ціль", small_bold), p(goal_name)],
        [p("Завдання", small_bold), p(task_name)],
        [p("Індикатор", small_bold), p(measure.get("indicator"))],
        [p("Одиниця виміру", small_bold), p(measure.get("unit"))],
        [p("Головний виконавець", small_bold), p(measure.get("department"))],
        [p("Співвиконавці", small_bold), p("; ".join(filter(None, [clean(measure.get("department_co_1")), clean(measure.get("department_co_2"))])))],
        [p("Строк виконання", small_bold), p(measure.get("period"))],
        [p("План 2026 / 2027 / 2028", small_bold), p(" / ".join(clean(measure.get(f"target_{year}")) or "—" for year in (2026, 2027, 2028)))],
        [p("Ручні закриття", small_bold), p(", ".join(closed_periods or []) or "—")],
    ]
    passport = Table(passport_rows, colWidths=[45 * mm, 132 * mm], repeatRows=0)
    passport.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Stage4DejaVu"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([passport, Spacer(1, 4 * mm), Paragraph("Поточний стан за періодами", h2)])

    req = requests_df.copy() if requests_df is not None else pd.DataFrame()
    if req.empty:
        story.append(p("Поданих відомостей немає."))
    else:
        req["_year"] = _series(req, "year").apply(clean)
        req["_quarter"] = _series(req, "quarter").apply(quarter_to_roman)
        if "submitted_at" in req.columns:
            req["_submitted"] = pd.to_datetime(req["submitted_at"], errors="coerce", utc=True)
            req = req.sort_values("_submitted", ascending=False)
        report_rows = [[p(x, small_bold) for x in ["Період", "Статус виконання", "Факт", "Статус погодження", "Прогрес / ризики"]]]
        for _, row in req.iterrows():
            fact = clean(row.get("numeric_value")) or clean(row.get("value_text")) or "—"
            narrative = clean(row.get("progress_text"))
            risks = clean(row.get("risks"))
            combined = narrative + (("\nРизики: " + risks) if risks else "")
            report_rows.append([
                p(f"{row['_quarter']} кв. {row['_year']}", small),
                p(row.get("status"), small),
                p(fact, small),
                p(row.get("approval_status"), small),
                p(combined, small),
            ])
        report_table = Table(report_rows, colWidths=[24 * mm, 30 * mm, 23 * mm, 34 * mm, 66 * mm], repeatRows=1)
        report_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Stage4DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(report_table)

    story.extend([Spacer(1, 4 * mm), Paragraph("Історія погодження", h2)])
    logs = logs_df.copy() if logs_df is not None else pd.DataFrame()
    if logs.empty:
        story.append(p("Історії погодження немає."))
    else:
        logs["_changed"] = pd.to_datetime(logs.get("changed_at"), errors="coerce", utc=True)
        logs = logs.sort_values("_changed")
        log_rows = [[p(x, small_bold) for x in ["Дата", "Дія", "Статус", "Ким змінено", "Коментар"]]]
        for _, row in logs.iterrows():
            status = clean(row.get("new_status")) or clean(row.get("old_status"))
            log_rows.append([
                p(format_kyiv_datetime(row.get("changed_at")), small),
                p(row.get("action"), small),
                p(status, small),
                p(clean(row.get("actor_name")) or clean(row.get("changed_by")), small),
                p(row.get("admin_comment"), small),
            ])
        log_table = Table(log_rows, colWidths=[28 * mm, 47 * mm, 31 * mm, 36 * mm, 35 * mm], repeatRows=1)
        log_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Stage4DejaVu"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(log_table)

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Stage4DejaVu", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(14 * mm, 8 * mm, f"Сформовано {kyiv_now().strftime('%d.%m.%Y %H:%M')} · ТЕСТОВИЙ РЕЖИМ")
        canvas.drawRightString(A4[0] - 14 * mm, 8 * mm, f"Сторінка {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Workflow analytics from the audit log
# ---------------------------------------------------------------------------

def _request_lookup(requests_df: pd.DataFrame) -> pd.DataFrame:
    if requests_df is None or requests_df.empty or "id" not in requests_df.columns:
        return pd.DataFrame(columns=["request_id", "department", "strat_code", "year", "quarter", "responsible_person", "approval_status", "submitted_at", "chain_stage", "approval_chain"])
    req = requests_df.copy()
    req["request_id"] = pd.to_numeric(req["id"], errors="coerce").astype("Int64")
    keep = [
        "request_id", "department", "strat_code", "year", "quarter", "responsible_person",
        "approval_status", "submitted_at", "chain_stage", "approval_chain",
    ]
    for col in keep:
        if col not in req.columns:
            req[col] = ""
    return req[keep].dropna(subset=["request_id"]).drop_duplicates("request_id", keep="last")


def _stage_from_actor(row: pd.Series) -> str:
    role_map = {
        "admin": "Координатор",
        "ssp_head": "Керівник ССП",
        "ssp_deputy": "Заступник керівника ССП",
        "super_admin": "Супер-адмін",
        "ssp": "Відповідальна особа від ССП",
    }
    role = clean(row.get("actor_role"))
    if role in role_map:
        return role_map[role]
    actor = clean(row.get("changed_by"))
    prefix = clean(actor.split("·", 1)[0]) if actor else ""
    if prefix:
        aliases = {
            "Адміністратор": "Координатор",
            "Керівник ССП": "Керівник ССП",
            "Заступник керівника ССП": "Заступник керівника ССП",
            "Супер-адмін": "Супер-адмін",
        }
        return aliases.get(prefix, prefix)
    action = clean(row.get("action"))
    match = re.search(r"ланкою «([^»]+)»", action)
    return match.group(1) if match else "Не визначено"


def build_return_analytics(logs_df: pd.DataFrame, requests_df: pd.DataFrame) -> dict[str, Any]:
    req = _request_lookup(requests_df)
    request_ids = set(req["request_id"].dropna().astype(int).tolist())
    logs = logs_df.copy() if logs_df is not None else pd.DataFrame()
    if logs.empty:
        returns = pd.DataFrame()
    else:
        logs["request_id"] = pd.to_numeric(_series(logs, "request_id"), errors="coerce").astype("Int64")
        logs = logs[logs["request_id"].isin(request_ids)]
        action = logs.get("action", pd.Series([""] * len(logs), index=logs.index)).astype(str)
        new_status = logs.get("new_status", pd.Series([""] * len(logs), index=logs.index)).astype(str)
        returns = logs[new_status.isin(schemes.ALL_RETURNED_STATUSES) | action.str.contains("Повернен", case=False, na=False)].copy()

    if returns.empty:
        return {
            "total_returns": 0,
            "average_per_request": 0.0,
            "by_department": pd.DataFrame(columns=["ССП", "Кількість повернень"]),
            "by_stage": pd.DataFrame(columns=["Ланка, що повернула", "Кількість повернень"]),
            "top_requests": pd.DataFrame(columns=["ID заявки", "Код заходу", "Період", "ССП", "Кількість повернень"]),
        }

    returns = returns.merge(req, on="request_id", how="left")
    returns["Ланка, що повернула"] = returns.apply(_stage_from_actor, axis=1)
    returns["ССП"] = returns["department"].apply(lambda x: clean(x) or "Не визначено")
    by_department = (
        returns.groupby("ССП", dropna=False).size().reset_index(name="Кількість повернень")
        .sort_values(["Кількість повернень", "ССП"], ascending=[False, True])
    )
    by_stage = (
        returns.groupby("Ланка, що повернула", dropna=False).size().reset_index(name="Кількість повернень")
        .sort_values("Кількість повернень", ascending=False)
    )
    top = (
        returns.groupby(["request_id", "strat_code", "year", "quarter", "ССП"], dropna=False)
        .size().reset_index(name="Кількість повернень")
        .sort_values(["Кількість повернень", "request_id"], ascending=[False, True])
    )
    top["ID заявки"] = top["request_id"].astype("Int64")
    top["Код заходу"] = top["strat_code"].apply(clean)
    top["Період"] = top.apply(lambda r: f"{quarter_to_roman(r['quarter'])} кв. {clean(r['year'])}", axis=1)
    top = top[["ID заявки", "Код заходу", "Період", "ССП", "Кількість повернень"]]
    denominator = max(len(req), 1)
    return {
        "total_returns": int(len(returns)),
        "average_per_request": round(len(returns) / denominator, 2),
        "by_department": by_department.reset_index(drop=True),
        "by_stage": by_stage.reset_index(drop=True),
        "top_requests": top.reset_index(drop=True),
    }


def _parse_chain_stage_label(raw_chain: Any, stage: Any, approval_status: Any) -> str:
    status = clean(approval_status)
    if status == schemes.STATUS_WAITING_MANAGER_SELECTION:
        return WAITING_STATUS_LABELS[status]
    chain = schemes.parse_chain(raw_chain)
    stage_idx = schemes.parse_stage(stage)
    item = schemes.current_stage(chain, stage_idx)
    if status == schemes.STATUS_COORDINATOR_REVIEW:
        item = schemes.current_stage(chain, schemes.coordinator_stage_index(chain))
    elif status == schemes.STATUS_MANAGER_REVIEW:
        manager_idx = schemes.manager_stage_index(chain)
        item = schemes.current_stage(chain, manager_idx) if manager_idx is not None else item
    elif status == schemes.STATUS_SUPERADMIN_REVIEW and clean((item or {}).get("role")) != "super_admin":
        item = next((part for part in chain if clean(part.get("role")) == "super_admin"), item)
    if item:
        label = clean(item.get("label") or schemes.STAGE_LABELS.get(item.get("role")))
        who = clean(item.get("name") or item.get("email"))
        return f"{label} ({who})" if label and who else (label or who or "Не визначено")
    return WAITING_STATUS_LABELS.get(status, status or "Не визначено")


def build_approval_speed_analytics(
    logs_df: pd.DataFrame,
    requests_df: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or kyiv_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=KYIV_TZ)
    now_utc = now.astimezone(timezone.utc)
    req = _request_lookup(requests_df)
    request_ids = set(req["request_id"].dropna().astype(int).tolist())
    logs = logs_df.copy() if logs_df is not None else pd.DataFrame()
    if logs.empty:
        logs = pd.DataFrame(columns=["request_id", "changed_at", "old_status", "new_status"])
    logs["request_id"] = pd.to_numeric(_series(logs, "request_id"), errors="coerce").astype("Int64")
    logs = logs[logs["request_id"].isin(request_ids)].copy()
    logs["_ts"] = pd.to_datetime(_series(logs, "changed_at"), errors="coerce", utc=True)
    logs = logs.dropna(subset=["_ts"]).sort_values(["request_id", "_ts"])

    final_rows: list[dict[str, Any]] = []
    for _, request in req.iterrows():
        rid = int(request["request_id"])
        submitted = pd.to_datetime(request.get("submitted_at"), errors="coerce", utc=True)
        request_logs = logs[logs["request_id"] == rid]
        final = request_logs[_series(request_logs, "new_status").astype(str) == "Погоджено"]
        if pd.notna(submitted) and not final.empty:
            final_time = final.iloc[0]["_ts"]
            if final_time >= submitted:
                final_rows.append({
                    "request_id": rid,
                    "days": (final_time - submitted).total_seconds() / 86400,
                })
    final_df = pd.DataFrame(final_rows)
    average_total = round(final_df["days"].mean(), 2) if not final_df.empty else 0.0

    stage_durations: list[dict[str, Any]] = []
    for _, request in req.iterrows():
        rid = int(request["request_id"])
        request_logs = logs[logs["request_id"] == rid]
        submitted = pd.to_datetime(request.get("submitted_at"), errors="coerce", utc=True)
        if request_logs.empty or pd.isna(submitted):
            continue
        first = request_logs.iloc[0]
        current_status = clean(first.get("old_status")) or clean(first.get("new_status"))
        entered_at = submitted
        for _, event in request_logs.iterrows():
            event_time = event["_ts"]
            old_status = clean(event.get("old_status"))
            new_status = clean(event.get("new_status"))
            if old_status == new_status:
                continue
            stage_status = old_status or current_status
            if stage_status in WAITING_STATUS_LABELS and event_time >= entered_at:
                stage_durations.append({
                    "request_id": rid,
                    "Ланка": _parse_chain_stage_label(
                        request.get("approval_chain"),
                        request.get("chain_stage"),
                        stage_status,
                    ),
                    "Днів": (event_time - entered_at).total_seconds() / 86400,
                })
            current_status = new_status
            entered_at = event_time
    stage_df = pd.DataFrame(stage_durations)
    if stage_df.empty:
        stage_average = pd.DataFrame(columns=["Ланка", "Середній час, днів", "Завершених проходжень"])
    else:
        stage_average = (
            stage_df.groupby("Ланка", dropna=False)
            .agg(**{"Середній час, днів": ("Днів", "mean"), "Завершених проходжень": ("Днів", "count")})
            .reset_index()
        )
        stage_average["Середній час, днів"] = stage_average["Середній час, днів"].round(2)
        stage_average = stage_average.sort_values("Середній час, днів", ascending=False)

    hanging_rows: list[dict[str, Any]] = []
    for _, request in req.iterrows():
        status = clean(request.get("approval_status"))
        if status not in WAITING_STATUS_LABELS:
            continue
        rid = int(request["request_id"])
        request_logs = logs[logs["request_id"] == rid]
        entries = request_logs[_series(request_logs, "new_status").astype(str) == status]
        entered = entries.iloc[-1]["_ts"] if not entries.empty else pd.to_datetime(request.get("submitted_at"), errors="coerce", utc=True)
        if pd.isna(entered):
            continue
        days = max((pd.Timestamp(now_utc) - entered).total_seconds() / 86400, 0)
        hanging_rows.append({
            "ID заявки": rid,
            "Код заходу": clean(request.get("strat_code")),
            "Період": f"{quarter_to_roman(request.get('quarter'))} кв. {clean(request.get('year'))}",
            "ССП": clean(request.get("department")) or "—",
            "Поточна ланка": _parse_chain_stage_label(request.get("approval_chain"), request.get("chain_stage"), status),
            "Днів на ланці": round(days, 2),
        })
    hanging = pd.DataFrame(hanging_rows)
    if not hanging.empty:
        hanging = hanging.sort_values("Днів на ланці", ascending=False).reset_index(drop=True)
    else:
        hanging = pd.DataFrame(columns=["ID заявки", "Код заходу", "Період", "ССП", "Поточна ланка", "Днів на ланці"])

    return {
        "average_total_days": average_total,
        "completed_requests": int(len(final_df)),
        "stage_average": stage_average.reset_index(drop=True),
        "hanging": hanging,
    }
