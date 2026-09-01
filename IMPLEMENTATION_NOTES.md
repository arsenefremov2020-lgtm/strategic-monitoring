# IMPLEMENTATION_NOTES — Presentation PDF parity

## Root cause
Dashboard had two independent presentation implementations. Browser Presentation mode was the current seven-slide HTML/CSS implementation in `pages/2_Dashboard.py`, while Dashboard PDF export built a legacy generic ReportLab presentation from separate `_pdf_kpis`, status/gauge figures and weighted-failure insights. The generic contract could not represent the current seven slides and duplicated selection/formatting logic.

Repository-wide verification also found one real non-Dashboard legacy consumer in `pages/3_Оцінка_МіО.py`. It is intentionally preserved on an explicitly named `build_legacy_presentation_pdf()`; Dashboard does not use that renderer.

## Changed files
- `pages/2_Dashboard.py` — builds one canonical presentation payload from the already-active Dashboard snapshot context; browser Presentation mode and Dashboard PDF consume it.
- `core/presentation.py` — canonical seven-slide payload contract and order validation.
- `core/exports.py` — Dashboard PDF renderer rewritten as a renderer-only consumer of the canonical payload; old generic renderer retained only as `build_legacy_presentation_pdf()` for the MIO consumer.
- `pages/3_Оцінка_МіО.py` — switched its existing generic PDF export to the explicit legacy renderer so the Dashboard contract change does not break MIO.
- `scripts/test_presentation_pdf.py` — presentation/PDF parity regression guards.
- `IMPLEMENTATION_NOTES.md` — this report.

## Canonical payload
The payload contains exactly these ordered slide keys:
`title → verdict → key_metrics → strategic_goals → risks → top5 → finance`.

The Dashboard captures `generated_at` once and stores the applied filter state in the same payload. The payload contains display-ready titles, subtitles, KPI cards, metric bars, goal rows, risk cards/tags, Top-5 rows and finance/KPKVK rows. Both renderers consume this same object.

The Dashboard PDF renderer does **not** call `_build_dashboard_context()`, does not recompute execution/coverage/risk metrics, does not aggregate finance independently, does not rank Top-5 independently and does not select a separate KPI list.

## Removed from Dashboard PDF production path
The Dashboard path no longer contains:
- `_pdf_kpis`;
- `_st_fig`;
- `_pdf_figures` with gauge charts;
- `_ins` weighted-failure insights;
- `conclusion_text[:110]`;
- the old generic multi-figure PDF contract.

The new Dashboard PDF is exactly seven 960×540 pages and follows:
`TITLE → VERDICT → KEY METRICS → STRATEGIC GOALS → RISKS → TOP-5 → FINANCE`.

## Regression results
GitHub Actions release gate run `33568473011`: **PASS**.

- Python compile gate: PASS for `core/presentation.py`, `core/exports.py`, `pages/2_Dashboard.py`, `pages/3_Оцінка_МіО.py`, `scripts/test_presentation_pdf.py`.
- `python scripts/test_presentation_pdf.py`: **PASS**.
- Existing `python scripts/test_dashboard_v2.py`: **PASS — 31 test groups**.
- Generated PDF regression check: **7 pages**, each `960×540`.
- Repository usage guard: Dashboard is the only production caller of the new `build_presentation_pdf(payload)`; MIO uses `build_legacy_presentation_pdf()`.

### CASE A — 2026 / III quarter / confirmed / all SSP
Regression payload verifies:
- total = 191;
- completed = 92;
- approved = 182;
- partly = 41;
- not submitted = 7;
- not done = 24;
- not time = 27;
- completion / goal execution / coverage values remain payload values;
- 8 strategic-goal rows;
- 5 Top-5 rows;
- finance groups and budget/KPKVK payload;
- PDF page count = 7.

These are regression fixtures matching the current control slice; CI does not independently recalculate the live Supabase dataset.

### CASE B — Q1
PASS: payload uses `mode="q1"`; Dashboard builds preliminary attention/forecast semantics from the existing `dashboard_risk_v2.risk_summary(active)`, not standard Q2/Q3 categories.

### CASE C — Q4
PASS: payload uses `mode="q4"`; Dashboard preserves the existing final annual result semantics.

### CASE D — operational source
PASS: the third KPI card accepts and renders `Пройшли координатора` from the same payload instead of hardcoding `Погоджено`.

### CASE E — specific SSP
PASS at contract/filter-propagation level: the applied department filter is stored in the same payload consumed by both renderers.

### CASE F — goal/task/product/deputy/source/financing/KPKVK filters
PASS at contract/filter-propagation level: all applied filter dimensions are captured in the canonical payload path; there is no separate unfiltered PDF context build.

## Visual smoke check
A PDF generated from the regression payload was rendered to PNG at 150 DPI and reviewed page-by-page:
- 7 pages present in the correct order;
- dark `#032A63` Presentation canvas;
- no legacy white template/footer/status page/gauge pages;
- Cyrillic text rendered;
- no visible clipping, overlap or square placeholder glyphs in the regression fixture.

A live browser-vs-PDF pixel comparison against the deployed Dashboard/Supabase session was not run by CI because it requires the interactive deployed session and live applied filters. The architecture now prevents data/structure drift by making both renderers consume the same presentation payload.

## Analytics scope
No production analytical calculations, Dashboard execution formulas, risk engine, finance engine, source resolution, status logic, denominators or threshold methodology were modified. Presentation-only shaping/rendering and the legacy PDF API split were changed.
