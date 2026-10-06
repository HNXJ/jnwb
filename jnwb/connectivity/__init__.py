"""
jnwb.connectivity -- functional connectivity, mutual information, and Granger causality.

Every estimator is modality-agnostic (LFP traces, binned spike counts, MUAe envelopes,
band-power time courses -- any regularly sampled series). ``CANONICAL_BANDS`` is imported from
``jnwb.spectral``.

Provides methods to compute directional functional connectivity metrics (bivariate Granger Causality),
Shannon Mutual Information between spike trains, and network graph analysis.

MI estimators:
- ``binary_occupancy`` — MI of per-bin spike presence (0/1); discards count/rate structure
- ``spike_count`` — MI of per-bin spike counts (discrete)

Granger returns residual diagnostics; optional ridge VAR; lag selection via AIC/BIC/HQIC.
Residual variance is the maximum-likelihood RSS / N, not RSS / (N - p): the Geweke measure
is a log ratio of ML variances, and the information criteria in ``_info_criterion`` carry
their own explicit parameter counts. This line read ``explicit N - p divisors`` while
``_residual_variance`` took an ``n_params`` argument it never used.

Modality-agnostic directed connectivity (added 2026-08-04)
---------------------------------------------------------
``granger`` / ``phase_slope_index`` / ``transfer_entropy`` all take the same
``(X, Y, ...)`` contract and return the same ``DirectedResult`` shape, so LFP
traces, binned spike counts, MUAe envelopes, band-power time courses and any
other regularly sampled series go through identical code:

    >>> import jnwb
    >>> jnwb.granger(v1_lfp, pfc_lfp, order='auto')          # (n_trials, n_times)
    >>> jnwb.granger_spectral(v1_lfp, pfc_lfp, fs=1000.0)    # Geweke, per band
    >>> jnwb.phase_slope_index(v1_lfp, pfc_lfp, fs=1000.0)   # frequency-resolved
    >>> jnwb.transfer_entropy(rate_a, rate_b, n_surrogates=200)
    >>> jnwb.bin_spikes(spike_times, (-0.5, 1.0), 10.0)      # spikes -> (trials, bins)

Sign convention is uniform: ``x_to_y`` is X -> Y (X leads / X predicts Y).

"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from .._dictlike import DictAccessMixin
from .._backend import (
    CPU,
    CUDA,
    resolve_device,
    warn_device_fallback,
    warn_no_gpu_path,
)
from .._parallel import parallel_map
from .._spread import is_constant, zscore
from .._units import resolve_unit_alias
from .._bins import bin_edges, right_open_counts, whole_bin_count
from .._layout import require_trial_length
from .._rng import Default, RNGLike, recorded_rng, resolve_seed_alias
from ..permutation import _TIE_RTOL, _count_at_least_as_extreme
from scipy import stats

log = logging.getLogger(__name__)

#: Settled band edges (Hz) -- single source of truth is jnwb.spectral.CANONICAL_BANDS;
#: re-exported here unchanged so this module's existing consumers and internal uses below
#: keep working without modification.
from ..spectral import CANONICAL_BANDS

from ._common import (
    _fixed_order,
    DirectedResult,
    _surrogate_rng,
    _MIN_TRIALS_FOR_TRIAL_PERMUTATION,
    _surrogate_scheme,
    _surrogate_source,
    _surrogate_p,
)
from ._trials import (
    as_trials,
    _pair_trials,
    _detrend_trials,
    _count_nonfinite_spikes,
    bin_spikes,
)
from ._information import (
    _discrete_mi_from_labels,
    spike_mutual_information,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
)
from ._granger import (
    _residual_variance,
    _ridge_lstsq,
    fit_var_bivariate,
    _info_criterion,
    select_optimal_lag,
    _ADF_NUMERICAL_FAILURES,
    _adf_pvalue,
    _ljung_box_pvalue,
    _series_diagnostics,
    granger_causality,
    _stack_var_design,
    _ols_rss,
    _sum_of_products,
    _granger_order_criteria,
    granger,
    _fit_var_matrix,
    _var_spectral_radius,
    granger_spectral,
    _spectral_gc_from_var,
)
from ._psi import (
    _welch_segments,
    _psi_from_spectra,
    _psi_leave_one_out,
    _psi_round_off,
    _warn_psi_zero_spread,
    phase_slope_index,
)
from ._transfer_entropy import (
    _discretize,
    _codes,
    _entropy_plugin_and_cells,
    _entropy_bits,
    _te_one_direction,
    transfer_entropy,
)
from ._network import (
    network_topology,
    DIRECTED_METHODS,
    directed_connectivity,
    directed_network,
)


# Public classes keep the module path they had before the split, so pickles and reprs
# that name it still resolve.
for _cls in (DirectedResult,):
    _cls.__module__ = __name__
del _cls
