"""
Statistical Analysis Module: Parametric + Non-parametric + family-wise FDR

API Layers
----------
**Exploratory** (``exploratory_compare``, ``exploratory_correlate``, ``exploratory_multi``):
    Dual parametric + non-parametric reporting for pilot analysis.
    Returns raw p-values only.  No q-values, no FDR correction applied.
    Use freely during exploration; do not cite these p-values as confirmatory.

**Confirmatory** (``confirmatory_compare``):
    Requires an explicit hypothesis string and alpha level.
    Returns BH-adjusted q-values suitable for cross-hypothesis family correction.
    Use StatisticalAnalysis.fdr_correct() on a *collection* of confirmatory p-values
    when testing many hypotheses (units / channels / frequencies / time bins).

**General Comparisons** (``compare_groups``, ``compare_multiple_groups``, ``correlate``):
    Core comparison routines returning both parametric and non-parametric statistics
    with explicit multiple_comparison status.

Revised: 2026-07-26 — Exploratory / Confirmatory API split
"""

from __future__ import annotations

import logging
import math
import warnings
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from .._parallel import parallel_map, spawn_seeds
from .._rng import DEFAULT_SEED, RNGLike, recorded_rng, resolve_rng
from .._rng import Default, REQUIRED, RNGLike, resolve_seed_alias
from .._spread import is_constant as _is_constant
import pandas as pd
from scipy import stats

from ..permutation import _count_at_least_as_extreme, permute_labels

log = logging.getLogger(__name__)

from ._tests import (
    clopper_pearson,
    mann_whitney_p_floor,
    exact_sign_flip,
    _require_shuffle_inputs,
    _tie_tolerance,
    _zero_spread_t,
    shuffle_pvalue_paired,
    _require_alternative,
    shuffle_pvalue_unpaired,
)
from ._firing import (
    _spike_window_bounds,
    fires_in_window,
    fire_indicator,
    paired_fire_prob_test,
    rate_in_window,
)
from ._trials import (
    detect_trial_cycles,
    assign_subblock_quartiles,
)
from ._analysis import (
    fdr_correct,
    _TEST_CHOICES,
    _CORRELATION_METHODS,
    _resolve_test_choice,
    StatisticalAnalysis,
)
from ._regression import (
    shuffle_r2_ci,
    coef_rows,
    _lag_align,
    _abs_pearson,
    cross_modal_comparison,
)
from ._cluster import (
    cluster_permutation_test,
)


# Public classes keep the module path they had before the split, so pickles and reprs
# that name it still resolve.
for _cls in (StatisticalAnalysis,):
    _cls.__module__ = __name__
del _cls
