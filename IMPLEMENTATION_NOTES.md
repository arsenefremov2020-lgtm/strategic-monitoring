# IMPLEMENTATION_NOTES — Presentation PDF parity

## Final status

Presentation PDF parity is accepted and release-gated.

Final verified GitHub Actions run:

- run: `33571605668`
- overall conclusion: **SUCCESS**
- head SHA: `3830c9b727291c4c3ea7cb2202e3272a31c1e094`

The Dashboard browser Presentation mode and Dashboard PDF export consume one canonical presentation payload. The PDF is an export renderer for the existing seven-slide Presentation mode; it does not recalculate Dashboard analytics.

## Canonical presentation architecture

The canonical slide order remains exactly:

`title → verdict → key_metrics → strategic_goals → risks → top5 → finance`

`pages/2_Dashboard.py` builds one `_presentation_payload = build_presentation_payload(...)`.

The same payload is then consumed by:

- browser Presentation mode through `build_presentation_html(_presentation_payload)`;
- Dashboard PDF through `build_presentation_pdf(_presentation_payload)`;
- presentation slide lookup through `presentation_slides_by_key(_presentation_payload)`.

No separate PDF analytics context was reintroduced. In particular, the Dashboard PDF production path does not independently rebuild KPIs, finance aggregation, risk semantics, source/status/filter state, gauges, weighted-failure insights, or Top-5 ranking.

## Dashboard PDF renderer

Dashboard PDF output is exactly **7 pages**.

Deterministic reference/output viewport:

`1366 × 768`

The ReportLab renderer follows the production Presentation CSS box model at that reference viewport, including:

- slide padding and vertical centering;
- CSS-derived typography scale;
- KPI/risk card geometry;
- metric/progress-bar proportions;
- strategic-goal flex proportions;
- Top-5 spacing and metadata layout;
- finance grid proportions;
- deterministic vector replacements for presentation markers/icons where an emoji font is not used.

Cyrillic remains PDF-safe. Text wrapping uses actual font metrics rather than character-count truncation.

The legacy MIO renderer remains separate and is not restyled into the Dashboard Presentation design.

## Browser renderer

`core/presentation.py` contains the canonical payload contract and the production Presentation HTML/CSS renderer.

Dashboard Presentation mode renders through `build_presentation_html(payload)`.

The browser-vs-PDF visual regression therefore compares the PDF against the same production Presentation HTML/CSS consumed by Dashboard, not against a duplicated test-only HTML implementation.

## MIO legacy compatibility

`pages/3_Оцінка_МіО.py` continues to use `build_legacy_presentation_pdf()`.

The legacy renderer retains the color constants required by its pre-existing ReportLab implementation:

- `BRAND_BLUE`
- `BRAND_YELLOW`
- `DARK`
- `GREY`

The release test performs an actual runtime call to `build_legacy_presentation_pdf(...)`, asserts that bytes are returned, and verifies the `%PDF` signature.

## Changed files

Final self-contained delivery files:

- `pages/2_Dashboard.py`
- `pages/3_Оцінка_МіО.py`
- `core/exports.py`
- `core/presentation.py`
- `scripts/test_presentation_pdf.py`
- `scripts/test_presentation_visual.py`
- `IMPLEMENTATION_NOTES.md`

## Final regression results

GitHub Actions run `33571605668` at head SHA
`3830c9b727291c4c3ea7cb2202e3272a31c1e094`: **SUCCESS**.

### Compile

Compile gate: **PASS**.

Changed Python files compiled successfully before runtime tests.

### Presentation/PDF semantic and content regression

Command:

`python scripts/test_presentation_pdf.py`

Result:

**PASS — 7 presentation/PDF test groups**

Exact passing groups:

1. `test_case_a_canonical_payload_and_pdf_content`
2. `test_q1_semantics_exact_and_rendered`
3. `test_q4_semantics_exact_and_rendered`
4. `test_operational_semantics_filter_label_value_and_pdf_text`
5. `test_mio_legacy_pdf_runtime_smoke`
6. `test_dashboard_uses_one_payload_for_browser_and_pdf`
7. `test_production_html_fixture_is_payload_driven`

These tests verify, among other things:

- canonical seven-slide order;
- Dashboard PDF page count = 7;
- Dashboard PDF page size = 1366×768;
- required text/content on every slide;
- control values `191`, `92`, `182`, `41`, `7`, `24`, `27`;
- strategic-goal values;
- risk counts/tags;
- full budget value `141.258414 млрд грн`;
- all six KPKVK rows in the stress fixture;
- confirmed-mode KPI label/value;
- operational-mode source state and its prepared KPI label/value;
- runtime MIO legacy PDF generation;
- one-payload browser/PDF contract.

### Q1 semantics

**PASS.**

The fixture and rendered PDF assert the exact Q1 presentation semantics:

- section: `Попередні сигнали I кварталу`;
- title: `Попередній прогноз без стандартної категоризації ризику`;
- cards:
  - `Сигнали уваги`;
  - `Сформовано попередніх прогнозів`;
  - `Стандартних категорій ризику`;
- standard risk categories count = `0`;
- preliminary attention tag is rendered;
- fourth KPI is `Середнє попереднє досягнення`.

### Q4 semantics

**PASS.**

The fixture and rendered PDF assert the exact Q4 presentation semantics:

- section: `Підсумок року`;
- title: `Фактичні річні результати`;
- cards:
  - `Результат не досягнуто`;
  - `Частково виконано`;
  - `Результат досягнуто`;
- annual non-achievement tag is rendered;
- fourth KPI is `Результатів досягнуто`.

### Operational semantics

**PASS.**

The operational fixture explicitly uses:

`data_source_mode = operational`

The test verifies:

- payload filter state;
- prepared operational KPI label `Пройшли координатора`;
- prepared operational KPI value;
- corresponding extracted PDF text;
- absence of the confirmed-mode `Погоджено` label in that operational PDF fixture.

## Browser-vs-PDF visual regression

Command:

`python scripts/test_presentation_visual.py presentation_visual_artifacts`

Result:

**PASS**

Comparison method:

- browser side: Chromium / Playwright;
- HTML source: production `build_presentation_html(payload)`;
- PDF side: Dashboard PDF rendered to PNG with PyMuPDF;
- browser and PDF render size: **1366×768**;
- same stress payload for both renderers.

Visual regression covers slides:

- 1 — title;
- 3 — key metrics;
- 5 — risks;
- 7 — finance.

The stress fixture includes:

- a long conclusion;
- 8 realistically long strategic-goal names;
- 5 long Top-5 measure names;
- all 6 KPKVK rows;
- full budget value `141.258414 млрд грн`.

Recorded CI values from run `33571605668`:

### Slide 1 — title

- browser bbox = `(64,188,705,580)`
- PDF bbox = `(63,188,709,580)`
- MAE = `0.0136`

### Slide 3 — key_metrics

- browser bbox = `(64,72,1302,696)`
- PDF bbox = `(63,68,1303,698)`
- MAE = `0.0134`

### Slide 5 — risks

- browser bbox = `(64,79,1302,691)`
- PDF bbox = `(63,79,1303,691)`
- MAE = `0.0073`

### Slide 7 — finance

- browser bbox = `(63,148,964,622)`
- PDF bbox = `(63,136,964,634)`
- MAE = `0.0207`

The visual gate compares content envelopes and major regions with tolerant raster-difference thresholds so font rasterization differences do not require zero pixel diff while layout proportions remain regression-protected.

## Existing Dashboard regression suite

Command:

`python scripts/test_dashboard_v2.py`

Result:

**PASS — 31/31 test groups**

This confirms that the Presentation/PDF refactor did not break the existing Dashboard regression suite.

## Production logic scope

The Presentation PDF parity work does **not** change:

- production analytics calculations;
- Dashboard formulas;
- risk methodology;
- finance calculations;
- source logic;
- status logic;
- filter logic.

The PDF remains a renderer-only consumer of already prepared presentation data.

## Release-gate conclusion

Final release evidence for run `33571605668`:

- overall workflow: **SUCCESS**;
- compile: **PASS**;
- presentation/PDF tests: **7/7 PASS**;
- exact Q1 semantics: **PASS**;
- exact Q4 semantics: **PASS**;
- operational semantics: **PASS**;
- MIO legacy runtime PDF smoke: **PASS**;
- canonical one-payload browser/PDF contract: **PASS**;
- browser-vs-PDF visual regression: **PASS**;
- Dashboard regression suite: **31/31 PASS**;
- packaging/upload steps: **PASS**.

The temporary Presentation PDF parity release-gate workflow is not part of the final production delivery package.
