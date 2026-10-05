"""
jnwb.spectral -- spectral/oscillatory analysis: band-limited power, cross-area coherence,
1/f tilt, imaginary coherency, and re-referencing for LFP time series.

All functions take plain time-series arrays and generic keyword parameters. ``CANONICAL_BANDS``
is the default band-edge table (theta/alpha/beta/gamma); override via ``freq_bands=`` on any
caller that accepts it.
"""

import logging
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import optimize, signal, stats
import pandas as pd

from .._dictlike import DictAccessMixin, RenamedKeyDict
from .._backend import CPU, CUDA, resolve_device, warn_device_fallback
from .._layout import require_channel_major
from .._parallel import parallel_map
from .._rng import DEFAULT_SEED, RNGLike, surrogate_rng
from ..permutation import _count_at_least_as_extreme
from .._spread import is_constant as _is_constant

from ._common import (
    _require_band_bins,
    _require_finite_nonempty_trace,
    _require_two_samples,
    _flat_as_zero,
    CANONICAL_BANDS,
    _resolve_fs,
    _require_positive_fs,
)
from ._psd import (
    _TILT_DC_FLOOR_HZ,
    _MIN_TILT_BINS,
    compute_psd,
    harmonic_analysis,
    spectral_tilt,
    AperiodicFitResult,
    aperiodic_fit,
    _welch_csd_gpu,
    compute_multitaper_psd,
)
from ._decibels import (
    _ratio_to_db,
    to_db,
    DB_AGGREGATIONS,
    RELATIVE_POWER_MODELS,
    aggregate_to_db,
    relative_power,
    band_power,
)
from ._coupling import (
    _require_equal_lengths,
    _require_1d_pair,
    _require_finite_nonempty_pair,
    ZERO_LAG_RTOL,
    _wpli_from_cross_spectra,
    _require_identifiable_segmentation,
    MIN_IDENTIFIABLE_SEGMENTS,
    MIN_COHERENCE_NPERSEG,
    welch_segment_count,
    cross_area_coherence,
    imaginary_coherency,
    wpli,
)
from ._reference import (
    _require_channel_permutation,
    bipolar_reference,
    laplacian_reference,
    voltage_curvature_1d,
    current_source_density_1d,
)

log = logging.getLogger(__name__)

# Public classes keep the module path they had before the split, so pickles and reprs
# that name it still resolve.
for _cls in (AperiodicFitResult,):
    _cls.__module__ = __name__
del _cls
