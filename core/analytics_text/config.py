from __future__ import annotations

"""Language-selection configuration for the analytics note generator.

IMPORTANT: the thresholds in this module are NOT canonical monitoring methodology,
KPI targets, official performance grades, or approved risk categories. They are
internal language/composition bands used only to choose how strongly the generator
may phrase an already calculated fact. Canonical values continue to come from the
existing dashboard/analytics calculations.

User-facing text must therefore avoid presenting these bands as formal categories
(e.g. "critical", "sufficient", "high-performing").
"""

# Internal linguistic bands only. Names deliberately say "band" rather than
# pretending to be approved business classifications.
EXECUTION_LANGUAGE_BANDS = {
    "top": 90.0,
    "upper": 75.0,
    "middle": 50.0,
    "lower": 25.0,
}

COVERAGE_LANGUAGE_BANDS = {
    "near_full": 95.0,
    "broad": 80.0,
    "partial": 60.0,
    "limited": 30.0,
}

DELTA_LANGUAGE_BANDS = {
    "strong": 15.0,
    "moderate": 7.0,
    "small": 2.0,
}

GAP_LANGUAGE_BANDS = {
    "very_wide": 35.0,
    "wide": 20.0,
    "moderate": 10.0,
}

CONCENTRATION_LANGUAGE_BANDS = {
    "majority": 0.50,
    "material": 0.33,
}

MISSING_SHARE_LANGUAGE_BANDS = {
    "large": 0.30,
    "material": 0.10,
}

PROBLEM_SHARE_LANGUAGE_BANDS = {
    "large": 0.25,
}

STATUS_SHARE_LANGUAGE_BANDS = {
    "material": 0.25,
}

VOLATILITY_LANGUAGE_BAND = 12.0

SAMPLE_THRESHOLDS = {
    "single": 1,
    "very_small": 5,
    "small": 15,
    "large": 80,
}

MAX_NAMED_ITEMS = 3
