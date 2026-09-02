"""Canonical Dashboard presentation model and browser renderer.

This module contains presentation-only shaping/rendering. It intentionally does
not calculate Dashboard analytics, risk, finance, source, status, or filter
semantics. Browser Presentation mode and PDF consume the same prepared payload.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

REFERENCE_WIDTH = 1366
REFERENCE_HEIGHT = 768

SLIDE_ORDER = (
    "title",
    "verdict",
    "key_metrics",
    "strategic_goals",
    "risks",
    "top5",
    "finance",
)


def build_presentation_payload(
    *,
    generated_at: datetime,
    applied_filters: Mapping[str, Any],
    title: Mapping[str, Any],
    verdict: Mapping[str, Any],
    key_metrics: Mapping[str, Any],
    strategic_goals: Mapping[str, Any],
    risks: Mapping[str, Any],
    top5: Mapping[str, Any],
    finance: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the one canonical, ordered model used by both renderers."""
    slides = [
        {"key": "title", **dict(title)},
        {"key": "verdict", **dict(verdict)},
        {"key": "key_metrics", **dict(key_metrics)},
        {"key": "strategic_goals", **dict(strategic_goals)},
        {"key": "risks", **dict(risks)},
        {"key": "top5", **dict(top5)},
        {"key": "finance", **dict(finance)},
    ]
    payload = {
        "version": 1,
        "generated_at": generated_at.isoformat(),
        "generated_at_display": generated_at.strftime("%d.%m.%Y %H:%M"),
        "applied_filters": dict(applied_filters),
        "slides": slides,
    }
    validate_presentation_payload(payload)
    return payload


def validate_presentation_payload(payload: Mapping[str, Any]) -> None:
    slides = list(payload.get("slides") or [])
    keys = tuple(str(slide.get("key") or "") for slide in slides)
    if keys != SLIDE_ORDER:
        raise ValueError(f"Presentation slide order must be {SLIDE_ORDER}, got {keys}")
    if len(slides) != 7:
        raise ValueError(f"Presentation payload must contain exactly 7 slides, got {len(slides)}")


def presentation_slides_by_key(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Convenience view for renderers; does not change canonical slide order."""
    validate_presentation_payload(payload)
    return {str(slide["key"]): slide for slide in payload["slides"]}


PRESENTATION_CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; min-height: 100%; }
body { background: #032A63; font-family: 'Helvetica Neue', Arial, sans-serif; overflow-x: hidden; }
.pres-overlay { min-height: 100vh; background: #032A63; overflow-y: auto; }
.pres-ua-bar { height: 3px; background: linear-gradient(90deg,#005BBB 50%,#FFD500 50%); width: 100%; }
.pres-nav { position: sticky; top: 0; z-index: 100; background: rgba(10,15,30,0.95); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(255,255,255,0.08); display: flex; align-items: center; justify-content: space-between; padding: 10px 32px; }
.pres-nav-title { color: rgba(255,255,255,0.5); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 600; }
.pres-nav-dots { display: flex; gap: 8px; align-items: center; }
.pres-dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,0.2); }
.pres-dot.active { background: #FFD500; width: 24px; border-radius: 4px; }
.pres-slide { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 48px 64px; position: relative; border-bottom: 1px solid rgba(255,255,255,0.04); }
.pres-slide:last-child { border-bottom: none; }
.pres-slide-num { position: absolute; top: 24px; right: 40px; font-size: 11px; color: rgba(255,255,255,0.2); letter-spacing: 0.1em; font-weight: 600; }
.pres-slide-title { background: #032A63; }
.pres-title-eyebrow { font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: #FFD500; font-weight: 700; margin-bottom: 20px; }
.pres-title-h1 { font-size: clamp(32px,4vw,56px); font-weight: 900; color: #fff; line-height: 1.1; margin-bottom: 16px; max-width: 800px; }
.pres-title-sub { font-size: clamp(14px,1.4vw,18px); color: rgba(255,255,255,0.5); max-width: 600px; line-height: 1.6; margin-bottom: 40px; }
.pres-filter-pills { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.pres-filter-pill { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); border-radius: 20px; padding: 6px 16px; font-size: 12px; color: rgba(255,255,255,0.7); font-weight: 600; }
.pres-slide-conclusion { background: #032A63; }
.pres-section-label { font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.35); font-weight: 700; margin-bottom: 24px; }
.pres-verdict-badge { display: inline-flex; align-items: center; gap: 10px; padding: 10px 24px; border-radius: 10px; font-size: clamp(18px,2vw,26px); font-weight: 900; margin-bottom: 20px; align-self: flex-start; }
.pres-verdict-badge.high { background: rgba(220,38,38,0.2); border: 1.5px solid #DC4A4A; color: #DC4A4A; }
.pres-verdict-badge.medium { background: rgba(217,119,6,0.2); border: 1.5px solid #FF7A45; color: #F4B400; }
.pres-verdict-badge.low { background: rgba(22,163,74,0.2); border: 1.5px solid #118847; color: #1E9E57; }
.pres-verdict-text { font-size: clamp(13px,1.2vw,16px); color: rgba(255,255,255,0.55); max-width: 680px; line-height: 1.7; margin-bottom: 40px; }
.pres-slide-kpis { background: #032A63; }
.pres-kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 20px; margin-top: 32px; }
.pres-kpi-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 6px; position: relative; overflow: hidden; }
.pres-kpi-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 14px 14px 0 0; }
.pres-kpi-card.blue::before { background: #4D8DFF; }
.pres-kpi-card.green::before { background: #00A8A8; }
.pres-kpi-card.red::before { background: #FF7A45; }
.pres-kpi-card.yellow::before { background: #F4B400; }
.pres-kpi-card.gray::before { background: #8A96A8; }
.pres-kpi-label { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(255,255,255,0.4); }
.pres-kpi-value { font-size: clamp(36px,4vw,56px); font-weight: 900; color: #fff; line-height: 1; }
.pres-kpi-sub { font-size: 13px; color: rgba(255,255,255,0.35); font-weight: 600; }
.pres-slide-goals { background: #032A63; }
.pres-goal-bar-wrap { margin-top: 28px; display: flex; flex-direction: column; gap: 14px; }
.pres-goal-row { display: flex; align-items: center; gap: 16px; }
.pres-goal-code { font-size: 11px; font-weight: 800; color: rgba(255,255,255,0.4); min-width: 36px; text-align: right; }
.pres-goal-name { font-size: 13px; color: rgba(255,255,255,0.7); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px; }
.pres-goal-bar-bg { flex: 2; background: rgba(255,255,255,0.06); border-radius: 99px; height: 10px; overflow: hidden; }
.pres-goal-bar-fill { height: 100%; border-radius: 99px; }
.pres-goal-pct { font-size: 13px; font-weight: 800; color: #fff; min-width: 44px; text-align: right; }
.pres-slide-risks { background: #032A63; }
.pres-risk-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin-top: 32px; }
.pres-risk-card { border-radius: 14px; padding: 28px 24px; display: flex; flex-direction: column; gap: 8px; }
.pres-risk-card.high { background: rgba(220,38,38,0.12); border: 1.5px solid rgba(220,38,38,0.3); }
.pres-risk-card.medium { background: rgba(217,119,6,0.1); border: 1.5px solid rgba(217,119,6,0.25); }
.pres-risk-card.low { background: rgba(22,163,74,0.1); border: 1.5px solid rgba(22,163,74,0.25); }
.pres-risk-label { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.pres-risk-card.high .pres-risk-label { color: #DC4A4A; }
.pres-risk-card.medium .pres-risk-label { color: #F4B400; }
.pres-risk-card.low .pres-risk-label { color: #1E9E57; }
.pres-risk-val { font-size: clamp(40px,5vw,64px); font-weight: 900; line-height: 1; }
.pres-risk-card.high .pres-risk-val { color: #DC4A4A; }
.pres-risk-card.medium .pres-risk-val { color: #F4B400; }
.pres-risk-card.low .pres-risk-val { color: #1E9E57; }
.pres-risk-sub { font-size: 13px; color: rgba(255,255,255,0.4); font-weight: 600; }
.pres-slide-h2 { font-size: clamp(24px,2.8vw,38px); font-weight: 900; color: #fff; margin-bottom: 4px; line-height: 1.15; }
.pres-slide-hsub { font-size: clamp(12px,1.1vw,15px); color: rgba(255,255,255,0.4); margin-bottom: 0; }
.pres-metric-rows { margin-top: 32px; display: flex; flex-direction: column; gap: 20px; }
.pres-metric-row { display: flex; align-items: center; gap: 20px; }
.pres-metric-label { font-size: 13px; font-weight: 700; color: rgba(255,255,255,0.55); min-width: 220px; }
.pres-metric-bar-bg { flex: 1; background: rgba(255,255,255,0.06); border-radius: 99px; height: 12px; overflow: hidden; }
.pres-metric-bar-fill { height: 100%; border-radius: 99px; }
.pres-metric-val { font-size: 16px; font-weight: 900; color: #fff; min-width: 56px; text-align: right; }
.pres-exit-hint { position: fixed; bottom: 24px; right: 32px; z-index: 200; background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 8px 16px; font-size: 11px; color: rgba(255,255,255,0.35); letter-spacing: 0.08em; pointer-events: none; }
"""


def _e(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def build_presentation_html(
    payload: Mapping[str, Any],
    *,
    include_ui: bool = True,
    single_slide_key: str | None = None,
) -> str:
    """Render production Presentation HTML from the canonical payload."""
    slides = presentation_slides_by_key(payload)
    title_slide = slides["title"]
    verdict_slide = slides["verdict"]
    metrics_slide = slides["key_metrics"]
    goals_slide = slides["strategic_goals"]
    risks_slide = slides["risks"]
    top5_slide = slides["top5"]
    finance_slide = slides["finance"]

    filter_pills_html = "".join(
        f'<span class="pres-filter-pill">{_e(p)}</span>'
        for p in title_slide.get("filter_pills", [])
    )
    verdict_cards_html = "".join(
        f"""
        <div class="pres-verdict-card" style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 18px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:8px;">{_e(item.get('label'))}</div>
            <div style="font-size:44px;font-weight:900;color:{_e(item.get('color') or '#FFFFFF')};line-height:1;">{_e(item.get('value_text'))}</div>
            <div style="font-size:12px;color:rgba(255,255,255,.35);margin-top:4px;">{_e(item.get('subtitle'))}</div>
        </div>"""
        for item in verdict_slide.get("cards", [])
    )
    metric_cards_html = "".join(
        f"""
        <div class="pres-kpi-card {_e(item.get('kind'))}">
            <div class="pres-kpi-label">{_e(item.get('label'))}</div>
            <div class="pres-kpi-value">{_e(item.get('value_text'))}</div>
            <div class="pres-kpi-sub">{_e(item.get('sub_text'))}</div>
        </div>"""
        for item in metrics_slide.get("cards", [])
    )
    metric_bars_html = ""
    for item in metrics_slide.get("bars", []):
        try:
            pct = min(max(float(item.get("value") or 0), 0), 100)
        except (TypeError, ValueError):
            pct = 0
        metric_bars_html += f"""
        <div class="pres-metric-row">
            <div class="pres-metric-label">{_e(item.get('label'))}</div>
            <div class="pres-metric-bar-bg"><div class="pres-metric-bar-fill" style="width:{pct}%;background:{_e(item.get('color'))};"></div></div>
            <div class="pres-metric-val">{_e(item.get('value_text'))}</div>
        </div>"""
    goal_rows_html = "".join(
        f"""
        <div class="pres-goal-row">
            <div class="pres-goal-code">{_e(row.get('code'))}</div>
            <div class="pres-goal-name" title="{_e(row.get('full_name'))}">{_e(row.get('name'))}</div>
            <div class="pres-goal-bar-bg"><div class="pres-goal-bar-fill" style="width:{float(row.get('value') or 0)}%;background:{_e(row.get('color'))};"></div></div>
            <div class="pres-goal-pct">{_e(row.get('value_text'))}</div>
        </div>"""
        for row in goals_slide.get("rows", [])
    )
    if not goal_rows_html:
        goal_rows_html = '<div style="color:rgba(255,255,255,0.3);margin-top:24px;">' + _e(goals_slide.get("empty_text")) + '</div>'
    risk_cards_html = "".join(
        f"""
        <div class="pres-risk-card {_e(item.get('kind'))}">
            <div class="pres-risk-label">{_e(item.get('label'))}</div>
            <div class="pres-risk-val">{_e(item.get('value_text'))}</div>
            <div class="pres-risk-sub">{_e(item.get('sub_text'))}</div>
        </div>"""
        for item in risks_slide.get("cards", [])
    )
    risk_tags_html = "".join(
        '<span style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:5px 12px;font-size:11px;color:rgba(255,255,255,.5);font-weight:600;">'
        + _e(tag) + '</span>'
        for tag in risks_slide.get("tags", [])
    )
    top5_html = ""
    for row in top5_slide.get("rows", []):
        top5_html += (
            '<div class="pres-top5-row" style="display:flex;align-items:flex-start;gap:14px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,0.06);">'
            f'<div class="pres-top5-badge" style="background:{_e(row.get("risk_color"))};color:#032A63;font-size:10px;font-weight:900;border-radius:6px;padding:3px 8px;white-space:nowrap;margin-top:2px;">{_e(row.get("risk_label"))}</div>'
            '<div style="flex:1;">'
            f'<div class="pres-top5-name" style="font-size:13px;color:rgba(255,255,255,0.85);font-weight:600;line-height:1.4;">{_e(row.get("name"))}</div>'
            '<div class="pres-top5-meta" style="display:flex;gap:10px;margin-top:5px;flex-wrap:wrap;">'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">📋 {_e(row.get("code"))}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">🏢 {_e(row.get("department"))}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">📊 {_e(row.get("status"))}</span>'
            f'<span style="font-size:10px;color:rgba(255,255,255,0.35);">🎯 Виконання: {_e(row.get("performance_text"))}</span>'
            '</div></div></div>'
        )
    if not top5_html:
        top5_html = '<div style="color:rgba(255,255,255,0.3);margin-top:24px;">' + _e(top5_slide.get("empty_text")) + '</div>'
    fin_bars_html = "".join(
        f"""
        <div class="pres-fin-source" style="margin-bottom:16px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
                <span style="font-size:13px;font-weight:700;color:rgba(255,255,255,.7);">{_e(item.get('label'))}</span>
                <span style="font-size:13px;font-weight:900;color:#fff;">{int(item.get('count') or 0)} <span style="font-size:11px;color:rgba(255,255,255,.35);">({float(item.get('percent') or 0)}%)</span></span>
            </div>
            <div style="background:rgba(255,255,255,.07);border-radius:99px;height:10px;overflow:hidden;"><div style="width:{float(item.get('percent') or 0)}%;height:100%;background:{_e(item.get('color'))};border-radius:99px;"></div></div>
        </div>"""
        for item in finance_slide.get("groups", [])
    )
    kpkvk_html = "".join(
        '<div class="pres-kpkvk-row" style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.06);">'
        f'<span style="font-size:14px;font-weight:800;color:#FFD500;">{_e(row.get("code"))}</span>'
        f'<span style="font-size:12px;color:rgba(255,255,255,.5);">{_e(row.get("count_text"))}</span>'
        f'<span style="font-size:12px;color:rgba(255,255,255,.7);font-weight:700;">{_e(row.get("budget_text"))}</span>'
        '</div>'
        for row in finance_slide.get("kpkvk_rows", [])
    )
    if not kpkvk_html:
        kpkvk_html = '<div style="color:rgba(255,255,255,.3);margin-top:12px;">' + _e(finance_slide.get("kpkvk_empty_text")) + '</div>'

    slide_html = {
        "title": f"""<div class="pres-slide pres-slide-title" data-slide-key="title">
            <div class="pres-slide-num">01 / 07</div>
            <div class="pres-title-eyebrow">{_e(title_slide.get('eyebrow'))}</div>
            <div class="pres-title-h1">{_e(title_slide.get('title'))}</div>
            <div class="pres-title-sub">{_e(title_slide.get('subtitle'))}</div>
            <div class="pres-filter-pills">{filter_pills_html}</div>
        </div>""",
        "verdict": f"""<div class="pres-slide pres-slide-conclusion {_e(verdict_slide.get('severity'))}" data-slide-key="verdict">
            <div class="pres-slide-num">02 / 07</div>
            <div class="pres-section-label">{_e(verdict_slide.get('section'))}</div>
            <div class="pres-verdict-badge {_e(verdict_slide.get('severity'))}">{_e(verdict_slide.get('emoji'))} {_e(verdict_slide.get('title'))}</div>
            <div class="pres-verdict-text">{_e(verdict_slide.get('text'))}</div>
            <div class="pres-verdict-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:680px;">{verdict_cards_html}</div>
        </div>""",
        "key_metrics": f"""<div class="pres-slide pres-slide-kpis" data-slide-key="key_metrics">
            <div class="pres-slide-num">03 / 07</div>
            <div class="pres-section-label">{_e(metrics_slide.get('section'))}</div>
            <div class="pres-slide-h2">{_e(metrics_slide.get('title'))}</div>
            <div class="pres-slide-hsub">{_e(metrics_slide.get('subtitle'))}</div>
            <div class="pres-kpi-grid">{metric_cards_html}</div>
            <div class="pres-metric-rows" style="max-width:680px;margin-top:40px;">{metric_bars_html}</div>
        </div>""",
        "strategic_goals": f"""<div class="pres-slide pres-slide-goals" data-slide-key="strategic_goals">
            <div class="pres-slide-num">04 / 07</div>
            <div class="pres-section-label">{_e(goals_slide.get('section'))}</div>
            <div class="pres-slide-h2">{_e(goals_slide.get('title'))}</div>
            <div class="pres-slide-hsub">{_e(goals_slide.get('subtitle'))}</div>
            <div class="pres-goal-bar-wrap">{goal_rows_html}</div>
        </div>""",
        "risks": f"""<div class="pres-slide pres-slide-risks" data-slide-key="risks">
            <div class="pres-slide-num">05 / 07</div>
            <div class="pres-section-label">{_e(risks_slide.get('section'))}</div>
            <div class="pres-slide-h2">{_e(risks_slide.get('title'))}</div>
            <div class="pres-slide-hsub">{_e(risks_slide.get('subtitle'))}</div>
            <div class="pres-risk-grid">{risk_cards_html}</div>
            <div class="pres-risk-summary" style="margin-top:48px;padding:24px 28px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;max-width:640px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:12px;">{_e(risks_slide.get('summary_label'))}</div>
                <div style="font-size:15px;color:rgba(255,255,255,.7);line-height:1.7;">{_e(risks_slide.get('summary_text'))}</div>
                <div style="margin-top:16px;display:flex;gap:12px;flex-wrap:wrap;">{risk_tags_html}</div>
            </div>
        </div>""",
        "top5": f"""<div class="pres-slide" style="background:#032A63;" data-slide-key="top5">
            <div class="pres-slide-num">06 / 07</div>
            <div class="pres-section-label">{_e(top5_slide.get('section'))}</div>
            <div class="pres-slide-h2">{_e(top5_slide.get('title'))}</div>
            <div class="pres-slide-hsub">{_e(top5_slide.get('subtitle'))}</div>
            <div class="pres-top5-list" style="margin-top:28px;max-width:860px;">{top5_html}</div>
        </div>""",
        "finance": f"""<div class="pres-slide" style="background:#032A63;" data-slide-key="finance">
            <div class="pres-slide-num">07 / 07</div>
            <div class="pres-section-label">{_e(finance_slide.get('section'))}</div>
            <div class="pres-slide-h2">{_e(finance_slide.get('title'))}</div>
            <div class="pres-slide-hsub">{_e(finance_slide.get('subtitle'))}</div>
            <div class="pres-fin-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:36px;max-width:900px;">
                <div>
                    <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:20px;">{_e(finance_slide.get('sources_label'))}</div>
                    {fin_bars_html}
                    <div class="pres-budget-card" style="margin-top:24px;background:rgba(0,91,187,.12);border:1px solid rgba(0,91,187,.25);border-radius:12px;padding:20px 22px;">
                        <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:8px;">{_e(finance_slide.get('budget', {}).get('label'))}</div>
                        <div style="font-size:36px;font-weight:900;color:#fff;line-height:1;">{_e(finance_slide.get('budget', {}).get('value_text'))}</div>
                        <div style="font-size:12px;color:rgba(255,255,255,.3);margin-top:4px;">{_e(finance_slide.get('budget', {}).get('subtitle'))}</div>
                    </div>
                </div>
                <div>
                    <div style="font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:20px;">{_e(finance_slide.get('kpkvk_label'))}</div>
                    {kpkvk_html}
                </div>
            </div>
        </div>""",
    }
    if single_slide_key:
        if single_slide_key not in slide_html:
            raise ValueError(f"Unknown presentation slide key: {single_slide_key}")
        body_content = slide_html[single_slide_key]
        ui_html = ""
        stripe = ""
    else:
        body_content = "".join(slide_html[key] for key in SLIDE_ORDER)
        stripe = '<div class="pres-ua-bar"></div>' if include_ui else ""
        ui_html = """
        <button id="pres-fs-btn" style="position:fixed;top:14px;right:16px;z-index:9999;font-family:'Segoe UI',system-ui,sans-serif;font-size:13px;font-weight:800;color:#fff;background:#005BBB;border:none;border-radius:10px;padding:8px 14px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.35);">⛶ На весь екран</button>
        <script>
          const _fsBtn = document.getElementById("pres-fs-btn");
          _fsBtn.addEventListener("click", () => {
            if (document.fullscreenElement) { document.exitFullscreen(); }
            else { document.documentElement.requestFullscreen(); }
          });
          document.addEventListener("fullscreenchange", () => {
            _fsBtn.textContent = document.fullscreenElement ? "✕ Вийти з повного екрана" : "⛶ На весь екран";
          });
        </script>
        <div class="pres-nav">
            <div class="pres-nav-title">Стратегічний моніторинг · Presentation mode</div>
            <div class="pres-nav-dots"><div class="pres-dot active"></div><div class="pres-dot"></div><div class="pres-dot"></div><div class="pres-dot"></div><div class="pres-dot"></div><div class="pres-dot"></div><div class="pres-dot"></div></div>
            <div style="font-size:11px;color:rgba(255,255,255,0.3);letter-spacing:.08em;">⬆ прокрутіть для перегляду слайдів</div>
        </div>
        <div class="pres-exit-hint">↑ прокрутіть вверх · вимкніть тумблер щоб вийти</div>
        """ if include_ui else ""
    return f"""<!DOCTYPE html>
<html lang="uk">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{PRESENTATION_CSS}</style></head>
<body><div class="pres-overlay">{stripe}{ui_html}{body_content}</div></body>
</html>"""
