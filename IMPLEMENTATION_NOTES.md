# RCv8 — FINAL RELEASE CLEANUP

## Final local SSP-label normalization cleanup

This post-acceptance pass changes **no methodology or numerical logic**. Relative to `strategic_monitoring_analytics_RCv8_RELEASE_FINAL.zip`, production logic changes only in `core/analytics_text/composer_overlay.py`, with the matching behavioral regression extension in `scripts/test_analytics_compatibility.py`.

Fourth local cleanup closed:

- active `ssp_drilldown` no longer builds `У портфелі ССП «{parent}» ...` directly; it now normalizes the factual parent through the existing `_dimension_label("department", parent)` path;
- `department="ССП 1"` therefore renders as `У портфелі ССП 1 ...`, never `У портфелі ССП «ССП 1» ...`;
- no new helper was introduced and no planner, finding disposition, factual methodology, scenario/signal, attention/risk, MіО, SSP-contribution, Dashboard, export or page behavior was changed;
- `CompatibilityNarrativeTests.test_one_ssp_with_multiple_children_survives_narrow_pruning` was extended end-to-end to assert that `ssp_drilldown` remains rendered, `ССП «ССП 1»` is absent, `ССП 1` is present, and the normalized drill-down sentence is present in `result.text`;
- the common compatibility invariant now also asserts that behavioral `result.text` contains none of `reference`, `best/worst`, or `ССП «ССП `.

Source audit of `core/analytics_text/composer_overlay.py` after the change:

- direct `ССП «{...}»` formatting remains only inside the canonical `_dimension_label()` helper itself;
- no active `"ССП «" + ...` concatenation path exists;
- no other active user-facing SSP wrapper requiring normalization was found.

## Final release cleanup (accepted RCv8 methodology unchanged)

This final packaging pass changes **no numerical, planner, compatibility, attention, risk-quarter, SSP-contribution, MіО, Dashboard or export methodology**. Relative to the accepted RCv8 archive, only three implementation areas changed:

1. `core/analytics_text/composer_overlay.py` — removed the user-facing technical fragments `reference` and `best/worst` in favor of fully Ukrainian wording; normalized already-prefixed SSP labels through `_dimension_label()` in unique portfolio and final-priority sentences, preventing `ССП «ССП 1»`.
2. `pages/9_Розрахунки.py` — removed the nested silent `except Exception: mio = {}` from factual-registry construction. A real `build_mio_analytics()` failure now reaches the surrounding visible diagnostics/error path instead of being converted into an empty MіО dataset. The MіО formulas are unchanged.
3. `scripts/test_analytics_comparative_extrema.py` — added user-facing language assertions (`reference` / `best/worst` absent from `result.text`) plus explicit regressions for the MіО error-propagation source contract and SSP-label normalization.

No other RCv8 solution file changed relative to the accepted RCv8 archive.

New/extended cleanup checks:

- `_assert_clean_pipeline`: every behavioral note produced by the comparative-extrema suite asserts `reference` and `best/worst` are absent from `result.text`.
- `test_calculations_page_does_not_swallow_mio_registry_errors` — PASS.
- `test_unique_ssp_portfolio_sentence_normalizes_prefixed_label` — PASS.


## Base and inputs

- **GitHub repository:** `arsenefremov2020-lgtm/strategic-monitoring`
- **Branch:** `main`
- **Exact production base commit:** `87277fe2755471cd3defb2efa622cffee25cd661`
- **HEAD verification:** `main` was rechecked before RCv8 work and still resolved to the exact commit above.
- **RCv7 input overlay:** `strategic_monitoring_analytics_RCv7_FINAL.zip`
- **RCv8 scope:** comparative extrema / superlative semantics only. Accepted execution, coverage, attention counts/classification, quarter-aware risk semantics, exact-latest SSP underperformance contribution, MіО numerical methodology, Dashboard methodology, exports, product restoration and the existing compatibility layer were not redesigned.

## Files in the final self-contained overlay

Every path below is included as a **complete repository-relative file**, not as a patch or fragment.

1. `core/analytics_calculations.py`
2. `core/analytics_text/__init__.py`
3. `core/analytics_text/analytical_metrics.py`
4. `core/analytics_text/compatibility.py`
5. `core/analytics_text/composer_overlay.py`
6. `core/analytics_text/context.py`
7. `core/analytics_text/findings_current.py`
8. `core/analytics_text/models.py`
9. `core/analytics_text/planner.py`
10. `core/analytics_text/scenarios_current.py`
11. `core/analytics_text/signals_current.py`
12. `core/analytics_text/validation.py`
13. `pages/7_Аналітика.py`
14. `pages/9_Розрахунки.py`
15. `scripts/test_analytics_compatibility.py`
16. `scripts/test_analytics_v3.py`
17. `scripts/test_analytics_edge_cases.py`
18. `scripts/test_analytics_comparative_extrema.py`
19. `IMPLEMENTATION_NOTES.md`

Relative to RCv7, production logic changes are intentionally concentrated in `core/analytics_text/analytical_metrics.py`, `core/analytics_text/composer_overlay.py`, and compatibility renderer metadata in `core/analytics_text/compatibility.py`. `scripts/test_analytics_v3.py` has two stale literal-string expectations updated to the new tie-safe MіО wording, and `scripts/test_analytics_comparative_extrema.py` is new. The remaining Analytics solution files are carried forward in full so the ZIP is self-contained relative to the production base.

## Defects closed

### 1. Goal / task / SSP execution extrema

Cross-sectional execution factual structures now explicitly expose comparative semantics rather than leaving the renderer to infer uniqueness from the first sorted row:

- `single_entity`
- `best_labels` / `worst_labels`
- `best_is_unique` / `worst_is_unique`
- `best_tie_count` / `worst_tie_count`
- `all_equal`
- exact `gap`
- `top3_boundary_unique` / `bottom3_boundary_unique`

When `gap == 0`, the renderer states that execution is equal and that there is no max-min gap. It does **not** call the distribution differentiated and does not choose an arbitrary best/worst entity. Tied extrema are rendered as tied groups.

The phrase that deviations cover a “помітну частину” is no longer triggered merely by more than one deviation. Renderer metadata `deviation_is_material` requires at least two deviations and at least half of the evaluated entities. The required regression with 10 entities and only 1 above + 1 below reference therefore does not make the “помітну частину” claim.

### 2. Product structure

`product` factual metadata now carries:

- `count` / `single_entity`
- `largest_labels`, `largest_is_unique`, `largest_tie_count`, `all_equal_size`
- `best_labels` / `worst_labels`, unique flags and tie counts
- `execution_count`, `all_equal_execution`, exact execution gap

One product is described without a portfolio-size or best/worst comparison. Equal portfolio size and equal execution are rendered explicitly as ties/equality. A unique superlative is emitted only when factual uniqueness is true.

`product_structure` remains a normal rendered finding and still reaches the existing `products` planner block. Product analysis was not removed or downgraded.

### 3. Status structure

`status` now exposes `dominant_labels`, `dominant_is_unique`, and `dominant_tie_count`. A 1/1 distribution is rendered as a tie with no unique most-common status. A single-status selection is described as a single observed status, without a comparative “most common” claim.

### 4. SSP portfolio impact

`ssp.portfolio` now exposes tied groups and uniqueness flags separately for:

- maximum portfolio weight;
- maximum underperformance contribution.

The detailed SSP paragraph and `final_assessment` consume those flags. Equal maxima are rendered as tied groups; the final synthesis no longer promotes the first tied SSP to “найбільш вагома негативна складова”. The previously accepted exact-latest calculation of Analytics SSP underperformance contribution is unchanged.

### 5. MіО interpretative layer

No MіО formulas were changed. Comparative metadata was added over the existing factual outputs:

- goals: `goals_count`, `single_entity`, tied best/worst codes, uniqueness flags, tie counts, `all_equal`, exact gap;
- tasks: `tasks_count`, `single_entity`, tied best/worst task codes, uniqueness flags, tie counts, `all_equal`, exact gap.

For one goal/task, no best/worst comparison is made. For equal/tied extrema, the renderer names the group or states equality. MіО execution/result, measure average/median and financing calculations remain unchanged.

### 6. Final synthesis

`final_assessment` now respects the same factual comparative semantics as the detailed blocks:

- equal strategic-goal execution (`gap == 0`) is stated as equality, not “стратегічні цілі мають різні результати”;
- tied SSP underperformance contribution is rendered as a tied maximum with no unique negative SSP;
- previously fixed missing-data tie semantics and current-management-attention semantics are preserved.

### 7. Additional superlative-audit closures

The source audit found two analogous active paths beyond the minimum requested cases:

- **wide-context SSP movement in the dynamics block**: the production base repeated scalar “largest increase / largest decrease” fields. Current `dynamics` is now adapted by `composer_overlay._dynamics_current_block`, which uses the tie-aware `department.change` factual metadata already used by the distribution renderer.
- **attention top-three wording at a tied 3/4 boundary**: factual metadata now exposes `top3_boundary_unique`. The accepted attention counts and concentration classification are unchanged; only the phrase “частка трьох найбільших позицій” is suppressed if rank 3 and rank 4 are tied.

Two legacy semantic-superlative regex rewrites were removed from `_language_cleanup()`. Comparative business logic is now decided by factual metadata and renderer branches, not by final-text replacement.

## Superlative source audit

Executed source search:

`rg -n -i "найвищ|найнижч|найбільш|найпошир|доміную|першочерг" core/analytics_text/composer.py core/analytics_text/composer_overlay.py`

The preserved production `composer.py` still physically contains legacy scalar-superlative branches because the production base is intentionally not rewritten. The **active current Analytics compose route** intercepts every relevant user-facing comparative block before final generation:

- `dynamics` → `composer_overlay._dynamics_current_block`
- `goals` / `tasks` / `departments` → `composer_overlay._distribution_current_block`
- `coverage` → `composer_overlay._coverage_current_block`
- `statuses` → `composer_overlay._statuses_current_block`
- `products` → `composer_overlay._products_current_block`
- `mio_assessment` → `composer_overlay._mio_current_block`
- `management_attention` → `composer_overlay._management_priorities_block` plus the current attention headline
- `final_assessment` → `composer_overlay._final_current_block`
- `overall_state` → `composer_overlay._overall_current_block`

The remaining active superlative phrases in the overlay are guarded by factual `*_is_unique`, tie-group metadata, rank-boundary metadata, or explicit single-entity/equality checks. Supporting-only findings are not handed to comparative legacy consumers.

## Compatibility audit

Static finding registry after RCv8:

- **75 supported finding codes**
- **65 `rendered`**
- **10 `supporting-only`**
- **0 `internal/ranking-only`**
- **0 undefined finding codes**

Behavioral compatibility corpus:

- **39 end-to-end contexts**
- **75/75 supported codes actually observed**
- **62 unique important findings (`importance >= 60`) observed**
- **62/62 important findings have a real rendered consumer in at least one applicable context**
- **2 important findings also exercise an explicit supporting-only runtime disposition in narrow/single-entity contexts**
- **0 unaccounted important findings**
- **0 `important_findings_skipped`**
- **0 validation warnings in the 39-context audit**
- **3152/3152 numeric provenance records valid**

The relevant behavioral test remains:

`CompatibilityRegistryBehaviorTests.test_all_75_supported_findings_have_behavioral_compatibility_path`

It checks actual `plan block -> renderer -> block.findings/used findings`, not registry string presence.

## New RCv8 behavioral regression suite

File: `scripts/test_analytics_comparative_extrema.py`

All tests run the full `context -> factual -> findings -> planner -> renderer -> validator -> final note` path.

Required scenarios:

1. `test_two_equal_goals_have_zero_gap_and_no_unique_extrema` — PASS
2. `test_three_equal_tasks_100_have_no_unique_extrema` — PASS
3. `test_two_equal_ssp_execution_50_has_no_unique_extrema` — PASS
4. `test_ten_entities_with_only_one_above_and_one_below_reference_are_not_material_deviation` — PASS
5. `test_single_product_has_no_largest_or_best_worst_comparison` — PASS
6. `test_two_equal_size_products_have_no_unique_largest_segment` — PASS
7. `test_two_equal_execution_products_have_no_unique_best_or_worst` — PASS
8. `test_status_one_to_one_has_no_unique_dominant_status` — PASS
9. `test_two_ssp_equal_portfolio_weight_have_no_unique_largest_ssp` — PASS
10. `test_two_ssp_equal_underperformance_contribution_have_no_unique_negative_ssp_in_final` — PASS
11. `test_mio_one_goal_has_no_best_worst_comparison` — PASS
12. `test_mio_two_equal_goals_have_no_unique_best_worst` — PASS
13. `test_mio_one_task_has_no_best_worst_comparison` — PASS
14. `test_mio_two_equal_tasks_have_no_unique_best_worst` — PASS

Additional audit scenarios:

15. `test_wide_department_movement_tie_has_no_arbitrary_unique_extremum` — PASS
16. `test_attention_top3_boundary_tie_does_not_claim_three_unique_largest_positions` — PASS

**Final comparative-extrema suite result after release cleanup: 18/18 PASS.**

## Regression tests actually run

- `PYTHONPATH=. python -m unittest scripts.test_analytics_v3 -q` → **70/70 PASS**
- `PYTHONPATH=. python -m unittest scripts.test_analytics_compatibility -q` → **35/35 PASS**, including the 75-code behavioral compatibility audit
- `PYTHONPATH=. python -m unittest scripts.test_analytics_edge_cases -q` → **10/10 PASS**
- `PYTHONPATH=. python -m unittest scripts.test_analytics_comparative_extrema -q` → **18/18 PASS**
- `PYTHONPATH=. python -m unittest scripts.test_analytics_v3.MioRegressionTests -q` → **14/14 PASS**
- `PYTHONPATH=. python scripts/test_dashboard_v2.py` → **31/31 Dashboard test groups PASS**
- Combined Analytics + RCv7 edge + RCv8 extrema check (`scripts.test_analytics_v3`, `scripts.test_analytics_edge_cases`, `scripts.test_analytics_comparative_extrema`) → **96/96 PASS**
- Compile gate for all Python files included in RCv8 ZIP → **18/18 PASS**
- Import smoke for core Analytics modules and test modules (pages excluded from import because UI imports are environment-dependent) → **16/16 PASS**

## Numerical / methodology preservation checks

Intentionally unchanged:

- exact-latest Analytics execution contract;
- average-range + exact-latest coverage contract;
- current attention numerical methodology and quarter semantics;
- Q1 preliminary / Q2-Q3 predictive / Q4 factual risk semantics;
- exact-latest SSP underperformance contribution calculation introduced before RCv8;
- MіО numerical methodology and restored fields;
- Dashboard methodology and `core/dashboard_risk.py`;
- exports, DOCX charts, workflow analytics, filters, access logic and page functionality carried by RCv7.

Byte comparison against the production snapshot confirms:

- `core/dashboard_risk.py` unchanged, SHA-256 `152ebdcb32dd8ffafb01bba342acbd58d1a8b75285ddb970af980b1fb3332d84`
- `core/mio_shared.py` unchanged, SHA-256 `53f07780cab407eb79d7380cf14b9844d547f2ad0727807f5f1d78f576a849d6`

## Retired-concept scan

Executed in the active current Analytics contract over `analytical_metrics.py`, `findings_current.py`, `signals_current.py`, `planner.py`, `composer_overlay.py`, `compatibility.py`, and `analytics_calculations.py` for:

- `is_problem_status`
- YoY / year-over-year
- active `problem_count` / problem concentration / problem drilldown
- temporal-average execution terminology
- “середнє виконання за квартал”

**Result: 0 matches in the active current Analytics contract.**

The preserved legacy production composer files are not claimed to have zero textual residue; they remain physically present in the repository but are not the current public finding contract and are not used to reintroduce retired Analytics concepts.

## Known limitations / skipped tests

No RCv8 comparative-extrema defect is known to remain after the behavioral and source audits above.

For this **fourth local SSP-label cleanup**, only the four Analytics suites requested by the user were rerun, together with the release-overlay compile and source checks listed below. Dashboard, standalone MіО, export and other production regressions were **not rerun in this cleanup pass** and are not newly reported as PASS here; their earlier results belong to the already accepted RCv8 baseline.

## Final packaging / replay status

For the accepted RCv8 archive **before this cleanup**, the package had already been overlaid on a newly copied clean production snapshot from the exact base commit and passed:

- package compile gate: **18/18 PASS**;
- combined `scripts.test_analytics_v3 + scripts.test_analytics_compatibility + scripts.test_analytics_edge_cases + scripts.test_analytics_comparative_extrema`: **131/131 PASS** (the comparative-extrema suite then contained 16 tests).

For this final cleanup pass, the original production ZIP bytes are not mounted in the current container, so a new physical clean-repository replay is **not claimed**. The exact final overlay is instead re-extracted and re-run with the unchanged production dependency interfaces supplied by the local test scaffold; those cleanup-pass results are reported below.

## Final cleanup execution note

Tests actually executed **after this fourth local SSP-label cleanup**:

- `PYTHONPATH=. python -m unittest scripts.test_analytics_v3 -q` → **70/70 PASS**
- `PYTHONPATH=. python -m unittest scripts.test_analytics_compatibility -q` → **35/35 PASS**
- `PYTHONPATH=. python -m unittest scripts.test_analytics_edge_cases -q` → **10/10 PASS**
- `PYTHONPATH=. python -m unittest scripts.test_analytics_comparative_extrema -q` → **18/18 PASS**
- combined run of the four suites above → **133/133 PASS**
- compile gate for every Python file in the distributable release overlay → **18/18 PASS**

Targeted end-to-end verification of the active narrow one-SSP drill-down produced:

- `ssp_drilldown` present in `result.debug.block_findings["departments"]`;
- normalized sentence `У портфелі ССП 1 фактично розрахований дочірній розподіл за завданнями ...`;
- `ССП «ССП ` absent from `result.text`;
- `reference` absent from `result.text`;
- `best/worst` absent from `result.text`.

Static release-cleanup checks:

- silent `except Exception: mio = {}` in `pages/9_Розрахунки.py` → **0 matches**;
- active direct SSP wrapper outside `_dimension_label()` → **0 matches**;
- package Python compile failures → **0**.

Exact archive replay for this fourth cleanup: the distributable ZIP was re-extracted over the local test scaffold and the four requested suites were rerun together → **133/133 PASS**; the 18 distributable Python files compiled from the re-extracted archive → **18/18 PASS**. The targeted one-SSP output from that replay retained `ssp_drilldown`, rendered `У портфелі ССП 1 ...`, and contained none of `reference`, `best/worst`, or `ССП «ССП `.

Environment note: the exact accepted RCv8 release overlay is present locally, while unchanged production-only imports required by the four test modules are supplied by the same local interface scaffold used for the preceding release-cleanup verification. This is therefore an exact **overlay-package replay**, not a newly claimed full physical production-repository replay. The accepted RCv8 methodology/base integration was not reconstructed or modified in this pass. No Dashboard/MіО/export regression is newly claimed here because the user requested only the four Analytics suites above.
