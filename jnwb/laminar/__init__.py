"""
jnwb.laminar -- Laminar electrophysiology analysis.

Provides validated computational primitives for cortical depth and laminar analysis:
- Vectorized Frequency-based Laminar Identity Profile (vFLIP): identifies the
  spectrolaminar crossover contact between supragranular gamma dominance and
  infragranular alpha/beta dominance along linear electrode array shafts.

References:
    Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
    potential power across the primate cortex. Nature Neuroscience.
    doi:10.1038/s41593-023-01554-7 -- the motif `vflip` tests for: gamma relative power
    peaks superficially, alpha-beta deep, and their crossover marks layer 4.
    `vflip` is not the paper's FLIP or its frequency-variable vFLIP, which share the name.
    The paper divides each frequency by the power of the channel with the highest power,
    uses 10-19 Hz and 75-150 Hz, and fits linear regressions over the channel range that
    maximizes a goodness of fit; vFLIP also searches over band pairs. `vflip` normalizes
    by the range across contacts, uses fixed default bands and scores the fit by its
    support score Omega, so its crossover is not a FLIP or vFLIP crossover.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .._dictlike import DictAccessMixin
from .._rng import Default, REQUIRED, RNGLike, resolve_seed_alias, surrogate_rng
from scipy import signal, stats
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import rankdata

from .._backend import CUDA, resolve_device, warn_no_gpu_path
from .._spread import is_constant
from ..permutation import _TIE_RTOL, _count_at_least_as_extreme, _count_each_at_least_as_extreme
from ..spectral import (
    MIN_COHERENCE_NPERSEG,
    _require_identifiable_segmentation,
    _wpli_from_cross_spectra,
)

from ._vflip import (
    CANONICAL_VFLIP_BANDS,
    VFlipResult,
    _DEPTH_AXES,
    _SHALLOW_ENDS,
    _MIN_FREQ_BINS,
    _refuse_a_deep_first_declaration,
    _depth_anchored_order,
    _unit_range,
    vflip,
    vflip_from_lfp,
)
from ._labels import (
    LAYER_BOUNDARY_TOL_CONTACTS,
    label_layers,
)
from ._xflip import (
    XFlipResult,
    _compute_correlation_matrix,
    _surrogate_phase_randomize,
    _compute_contrast,
    _select_count_by_min_p,
    _optimal_contiguous_partition,
    _label_change_boundaries,
    _partition_is_contiguous,
    _unrestricted_partition,
    xflip,
)
from ._zflip import (
    ZFlipResult,
    _ZFLIP_ORIENTATIONS,
    _LINEAR_ROUNDOFF_EPS,
    _linear_to_roundoff,
    zflip,
)

log = logging.getLogger(__name__)

# Public classes keep the module path they had before the split, so pickles and reprs
# that name it still resolve.
for _cls in (VFlipResult, XFlipResult, ZFlipResult):
    _cls.__module__ = __name__
del _cls
