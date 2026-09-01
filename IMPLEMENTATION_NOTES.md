# IMPLEMENTATION_NOTES — Presentation PDF parity

## Root cause
Dashboard had two independent presentation implementations. Browser Presentation mode was the current seven-slide HTML/CSS implementation in `pages/2_Dashboard.py`, while PDF export built a legacy generic ReportLab presentation from separate `_pdf_kpis`, status/gauge figures and weighted-failure insights. The legacy contract could not represent the current seven slides and duplicated selection/formatting logic.

## Changed files
- `pages/2_Dashboard.py` — builds one canonical presentation payload from the already-active Dashboard snapshot context; HTML and PDF consume it.
- `core/presentation.py` — canonical seven-slide payload contract and validation.
- `core/exports.py` — PDF renderer rewritten as a renderer-only consumer of the canonical payload.
- `scripts/test_presentation_pdf.py` — parity/regression checks for slide count/order, regression values, Q1/Q4 mode payloads, operational approval label and filter propagation.

## Canonical payload
The payload contains exactly these ordered slide keys:
`title → verdict → key_metrics → strategic_goals → risks → top5 → finance`.

The Dashboard captures `generated_at` once and stores applied filter state in the same payload. PDF does not call `_build_dashboard_context()`, does not aggregate finance independently, does not rank Top-5 independently and does not recalculate Dashboard/risk metrics.

## Analytics scope
No production analytical formulas, Dashboard execution formulas, risk engine, finance engine, source resolution or status logic were modified. Presentation-only shaping was centralized.

## Regression status
Automated release-gate run is pending in this branch. Final results will be recorded here after the run.
