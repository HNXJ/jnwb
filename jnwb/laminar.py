"""
jnwb.laminar -- Laminar electrophysiology analysis.

Provides validated computational primitives for cortical depth and laminar analysis:
- Vectorized Frequency-based Laminar Identity Profile (vFLIP): identifies the
  spectrolaminar crossover contact between supragranular gamma dominance and
  infragranular alpha/beta dominance along linear electrode array shafts.

References:
    Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
    potential power across the primate cortex. Nature Neuroscience.
    doi:10.1038/s41593-023-01554-7
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from ._dictlike import DictAccessMixin
from ._rng import Default, REQUIRED, RNGLike, resolve_seed_alias
from scipy import signal, stats
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import rankdata

from ._backend import CUDA, resolve_device, warn_no_gpu_path
from .spectral import (
    MIN_COHERENCE_NPERSEG,
    _require_identifiable_segmentation,
    _wpli_from_cross_spectra,
)

log = logging.getLogger(__name__)

CANONICAL_VFLIP_BANDS: Dict[str, Tuple[float, float]] = {
    "low": (8.0, 30.0),    # infragranular (deep) alpha/beta dominance
    "high": (50.0, 150.0),  # supragranular (superficial) gamma dominance
}


@dataclass(frozen=True)
class VFlipResult(DictAccessMixin):
    """Container for Vectorized Frequency-based Laminar Identity Profile (vFLIP) results.

    Attributes:
        crossover_contact: Continuous sub-contact coordinate where the spectrolaminar profile
            crosses zero between low-frequency and high-frequency dominance peaks, or None if rejected.

            The estimate is shrunk toward the centre of the sampled shaft, and the shrinkage
            grows as SNR falls. Regressing the estimate on the truth over a 24-contact shaft
            with the crossover placed from 20% to 80% of its length gives a slope of 0.703 at
            SNR 20, 0.804 at SNR 100 and 0.864 at SNR 1000, against 1.0 for an unbiased
            locator. At SNR 20 that is a mean signed error of +2.40 contacts for a crossover
            at 20% of the shaft and -1.87 contacts at 80%. Both band depth profiles
            are dominated by bins carrying no laminar source, so the per-trial min-max range
            comes from noisy extremes and compresses each profile toward its interior,
            pulling the crossing inward; this is attenuation, not a fixed offset. Treat a
            crossover reported near either end of the shaft as a bound rather than a point
            estimate, and prefer a probe whose span brackets the transition. Measured in
            `artifacts/benchmarks/vflip_calibration_0.2.4.md`.
        crossover_depth_um: Physical cortical depth of the crossover in micrometers (um) along
            the ordered contacts, or None if rejected or contact spacing is unavailable.
        support_score: Support metric Omega evaluating contrast magnitude, peak separation,
            and transition sharpness. Returned for both accepted and rejected fits.
        profile: 1D array of shape (n_channels,) containing the spectrolaminar difference
            profile Delta(c) along the ordered contacts, built from the two band depth
            profiles after each is rescaled to [0, 1]. Its zero crossing is the reported
            crossover_contact.
        low_peak_contact: Integer contact index of the low-frequency (alpha/beta) power peak.
        high_peak_contact: Integer contact index of the high-frequency (gamma) power peak.
        orientation: Resolved orientation string ('superficial_to_deep' or 'deep_to_superficial').
        accepted: Boolean flag indicating whether the spectrolaminar motif satisfies all
            acceptance criteria (support score >= threshold, valid monotonic crossover).
        rejection_reason: Diagnostic reason string if rejected, or None if accepted.
        n_channels: Total number of evaluated contacts along the probe shaft.
        n_missing: Number of bad or missing contacts interpolated or masked during fitting.
        bad_channel_mask: Optional boolean array of shape (n_channels,) indicating bad or
            masked contacts in input channel order.
    """

    crossover_contact: Optional[float]
    crossover_depth_um: Optional[float]
    support_score: float
    profile: np.ndarray
    low_peak_contact: Optional[int]
    high_peak_contact: Optional[int]
    orientation: str
    accepted: bool
    rejection_reason: Optional[str]
    n_channels: int
    n_missing: int
    bad_channel_mask: Optional[np.ndarray] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "crossover_contact": self.crossover_contact,
            "crossover_depth_um": self.crossover_depth_um,
            "support_score": float(self.support_score),
            "profile": self.profile.copy(),
            "low_peak_contact": int(self.low_peak_contact) if self.low_peak_contact is not None else None,
            "high_peak_contact": int(self.high_peak_contact) if self.high_peak_contact is not None else None,
            "orientation": str(self.orientation),
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "n_channels": int(self.n_channels),
            "n_missing": int(self.n_missing),
        }


def _unit_range(values: np.ndarray) -> np.ndarray:
    """Rescale a depth profile to span [0, 1] across contacts.

    Used to strip each analysis band's own additive background level and gain before the
    two depth profiles are differenced to locate the crossover. Unlike mean- or
    sum-constrained normalizations it leaves the profile's spatial mean free, which is
    what carries the location of the transition.
    """
    lo = float(np.min(values))
    hi = float(np.max(values))
    span = hi - lo
    if span < 1e-12:
        return np.zeros_like(values)
    return (values - lo) / span


def vflip(
    psd: np.ndarray,
    freqs: np.ndarray,
    *,
    band_low: Tuple[float, float] = CANONICAL_VFLIP_BANDS["low"],
    band_high: Tuple[float, float] = CANONICAL_VFLIP_BANDS["high"],
    contact_spacing: Optional[float] = None,
    probe_geometry: Optional[Any] = None,
    orientation: str = "auto",
    min_support_score: float = 3.75,
    bad_channel_mask: Optional[np.ndarray] = None,
    min_channels: int = 8,
    min_peak_distance: int = 2,
    device: str = "cpu",
) -> VFlipResult:
    """Vectorized Frequency-based Laminar Identity Profile (vFLIP).

    Estimates the spectrolaminar transition (layer 4 / granular crossover) along a linear
    multichannel probe from precomputed power spectral density (PSD) profiles.

    Evaluates the canonical spectrolaminar motif (Mendoza-Halliday et al. 2024), where
    supragranular (superficial) layers exhibit predominant high-frequency (gamma) power
    and infragranular (deep) layers exhibit predominant low-frequency (alpha/beta) power.

    Mathematical Estimator:
        1. Expresses power as relative power per frequency across contacts along the
           shaft: :math:`\\tilde{P}(c, f) = (P(c, f) - \\min_k P(k, f)) /
           (\\max_k P(k, f) - \\min_k P(k, f))`. Through 0.2.3 this was a columnwise
           z-score, which forced every column to zero mean across contacts and so pinned
           the crossing of :math:`\\Delta(c)` near the centre of the sampled contacts
           whatever the true crossover was; see the 0.2.4 entry in `CHANGELOG.md`.
        2. Computes low-band and high-band power profiles across contacts:
           :math:`L(c) = \\frac{1}{|F_{\\text{low}}|} \\sum_{f \\in F_{\\text{low}}} \\tilde{P}(c, f)`,
           :math:`H(c) = \\frac{1}{|F_{\\text{high}}|} \\sum_{f \\in F_{\\text{high}}} \\tilde{P}(c, f)`.
        3. Rescales each depth profile to :math:`[0, 1]` across contacts, removing the
           differing additive background the two analysis bands contribute, then forms
           the signed spectrolaminar difference profile
           :math:`\\Delta(c) = \\hat{H}(c) - \\hat{L}(c)` (oriented superficial to deep).
           The support score below deliberately uses the unrescaled profiles, since
           rescaling gives a pure noise profile the same range as a real motif.
        4. Identifies continuous sub-contact zero-crossing root :math:`c^*`:
           :math:`c^* = i + \\frac{-\\Delta(i)}{\\Delta(i+1) - \\Delta(i)}`
           located between the high-frequency peak :math:`c_{\\text{high}}` and low-frequency peak :math:`c_{\\text{low}}`.
        5. Evaluates the support score :math:`\\Omega` density-normalized to a canonical 24-contact reference
           baseline (:math:`(N/24)^{1.5}`) based on contrast magnitude, fractional spatial peak separation,
           and RMS difference profile across contacts, with each frequency-dependent term
           normalized for the number of contributing bins so the score's null does not
           move with recording length or `nperseg`. If :math:`\\Omega < \\Omega_{\\text{thresh}}` or no valid
           crossover exists, the fit is rejected (`accepted=False`, `crossover_contact=None`).

    Args:
        psd: 2D array of power spectral densities, shape `(n_channels, n_freqs)`.
            Must be finite and strictly non-negative.
        freqs: 1D array of strictly increasing frequency coordinates in Hz, shape `(n_freqs,)`.
        band_low: Frequency range (f_min, f_max) in Hz for the low-frequency band (default: 8-30 Hz).
        band_high: Frequency range (f_min, f_max) in Hz for the high-frequency band (default: 50-150 Hz).
        contact_spacing: Inter-contact spacing (pitch) in micrometers (um).
        probe_geometry: Optional :class:`jnwb.ProbeGeometry` object validating probe linearity and
            contact ordering along the shaft.
        orientation: Expected shaft orientation relative to channel indexing:
            - ``"auto"``: Automatically evaluates peak ordering and resolves orientation.
            - ``"superficial_to_deep"``: Requires contact 0 to be superficial (gamma peaks before alpha/beta).
            - ``"deep_to_superficial"``: Requires contact 0 to be deep (alpha/beta peaks before gamma).
        min_support_score: Minimum support score Omega required to accept the fit (default: 3.75).
            Must be a finite float; no sentinels (e.g. -inf) may bypass acceptance logic.
        bad_channel_mask: Optional boolean mask of shape `(n_channels,)` flagging invalid/detached contacts.
        min_channels: Minimum number of valid channels required along the shaft (default: 8).
        min_peak_distance: Minimum channel distance required between low and high power peaks (default: 2).
        device: Hardware device (`"cpu"` or `"cuda"`).

    Returns:
        :class:`VFlipResult` containing the estimated crossover contact, depth, support score,
        and diagnostic flags.

    Raises:
        ValueError: If input dimensions are invalid, frequencies non-monotonic, bands overlapping
            or outside frequency range, non-finite parameters provided, or min_support_score is non-finite.
    """
    # 1. Parameter validation
    if not np.isfinite(min_support_score):
        raise ValueError(f"min_support_score must be a finite float, got {min_support_score}")

    valid_orientations = ("auto", "superficial_to_deep", "deep_to_superficial")
    if orientation not in valid_orientations:
        raise ValueError(f"orientation must be one of {valid_orientations}, got {orientation!r}")

    # Validate device. `laminar.py` contains no cupy or torch call anywhere, so a
    # `device='cuda'` request can never be honoured here -- the resolver's answer used
    # to be assigned to `_` and thrown away, which meant a caller with no GPU was warned
    # and a caller with a working A4000 was not.
    if resolve_device(device, context="vflip", prefer="cupy", stacklevel=3) == CUDA:
        warn_no_gpu_path("vflip", "vflip has no GPU implementation", stacklevel=3)

    freqs_arr = np.asarray(freqs, dtype=np.float64)
    if freqs_arr.ndim != 1:
        raise ValueError(f"freqs must be 1D, got ndim={freqs_arr.ndim}")
    if len(freqs_arr) < 4:
        raise ValueError(f"freqs must have at least 4 frequency bins, got {len(freqs_arr)}")
    if not np.all(np.isfinite(freqs_arr)):
        raise ValueError("freqs contains non-finite (NaN or Inf) values")
    if not np.all(np.diff(freqs_arr) > 0):
        raise ValueError("freqs must be strictly increasing")

    # Validate bands
    if len(band_low) != 2 or len(band_high) != 2:
        raise ValueError(f"band_low and band_high must be 2-tuples, got {band_low} and {band_high}")
    l_min, l_max = float(band_low[0]), float(band_low[1])
    h_min, h_max = float(band_high[0]), float(band_high[1])
    if l_min <= 0 or h_min <= 0 or l_min >= l_max or h_min >= h_max:
        raise ValueError(f"Invalid band ranges: band_low=({l_min}, {l_max}), band_high=({h_min}, {h_max})")
    if l_max > h_min:
        raise ValueError(f"band_low ({band_low}) and band_high ({band_high}) must not overlap (l_max <= h_min)")

    mask_low = (freqs_arr >= l_min) & (freqs_arr <= l_max)
    mask_high = (freqs_arr >= h_min) & (freqs_arr <= h_max)
    n_low_bins = int(np.sum(mask_low))
    n_high_bins = int(np.sum(mask_high))
    if n_low_bins < 2:
        raise ValueError(f"Insufficient frequency bins in band_low ({band_low}): found {n_low_bins}, minimum 2")
    if n_high_bins < 2:
        raise ValueError(f"Insufficient frequency bins in band_high ({band_high}): found {n_high_bins}, minimum 2")

    # Validate PSD
    psd_arr = np.asarray(psd, dtype=np.float64)
    if psd_arr.ndim != 2:
        raise ValueError(f"psd must be a 2D array of shape (n_channels, n_freqs), got shape {psd_arr.shape}")
    n_channels, n_freqs = psd_arr.shape
    if n_freqs != len(freqs_arr):
        raise ValueError(f"psd n_freqs ({n_freqs}) does not match freqs length ({len(freqs_arr)})")
    if np.any(psd_arr < 0):
        raise ValueError("psd contains negative values. Power must be non-negative.")

    # Validate geometry
    effective_spacing = contact_spacing
    order = None
    if probe_geometry is not None:
        if not getattr(probe_geometry, "is_linear", False):
            raise ValueError("probe_geometry must describe a linear electrode shaft (is_linear=True)")
        if len(probe_geometry.channel_ids) != n_channels:
            raise ValueError(
                f"probe_geometry channel count ({len(probe_geometry.channel_ids)}) "
                f"does not match psd channels ({n_channels})"
            )
        if effective_spacing is None:
            effective_spacing = probe_geometry.nominal_pitch
        order = getattr(probe_geometry, "linear_order", None)

    if effective_spacing is not None:
        effective_spacing = float(effective_spacing)
        if effective_spacing <= 0 or not np.isfinite(effective_spacing):
            raise ValueError(f"contact_spacing must be strictly positive and finite, got {effective_spacing}")

    # 2. Bad channel and missing contact handling
    if bad_channel_mask is None:
        bad_mask = np.zeros(n_channels, dtype=bool)
    else:
        bad_mask = np.asarray(bad_channel_mask, dtype=bool).ravel()
        if len(bad_mask) != n_channels:
            raise ValueError(f"bad_channel_mask length ({len(bad_mask)}) != n_channels ({n_channels})")

    # Automatically flag non-finite channels as bad
    non_finite_rows = ~np.all(np.isfinite(psd_arr), axis=1)
    bad_mask = bad_mask | non_finite_rows

    effective_bad_input = bad_mask.copy()

    # If probe_geometry is provided, order channels along the physical shaft
    if order is not None and len(order) == n_channels:
        psd_work = psd_arr[order]
        bad_mask = bad_mask[order]
    else:
        psd_work = psd_arr

    n_missing = int(np.sum(bad_mask))
    n_valid = n_channels - n_missing

    if n_valid < min_channels:
        # Rejection: insufficient valid channels (eliminate fabricated values)
        nan_profile = np.full(n_channels, np.nan)
        return VFlipResult(
            crossover_contact=None,
            crossover_depth_um=None,
            support_score=-np.inf,
            profile=nan_profile,
            low_peak_contact=None,
            high_peak_contact=None,
            orientation="undetermined",
            accepted=False,
            rejection_reason="insufficient_channels",
            n_channels=n_channels,
            n_missing=n_missing,
            bad_channel_mask=effective_bad_input,
        )

    # 3. Frequency standardization across valid contacts along the shaft
    clean_psd = psd_work.copy()
    # Interpolate missing channels along depth before standardization
    valid_idx = np.where(~bad_mask)[0]
    if n_missing > 0:
        for f_idx in range(n_freqs):
            clean_psd[:, f_idx] = np.interp(np.arange(n_channels), valid_idx, clean_psd[valid_idx, f_idx])

    # Express the PSD relative to its largest value first. Z-scoring is unchanged by that
    # rescaling except where the std floor below applies; with the floor applied to the raw PSD
    # the result depended on amplitude units (a motif accepted at unit scale was rejected when
    # the same LFP was expressed in volts).
    psd_scale = float(np.max(np.abs(clean_psd)))
    if psd_scale > 0:
        clean_psd = clean_psd / psd_scale

    # Min-max normalize per frequency across contacts, to relative power in [0, 1].
    #
    # This replaces the columnwise z-score used through 0.2.3. Z-scoring forces every
    # frequency column to zero mean across contacts, so both band profiles carry zero
    # spatial mean and the difference profile Delta(c) = H(c) - L(c) sums to zero
    # identically. The zero crossing of a zero-sum profile sits near the centre of the
    # sampled contacts whatever the true crossover is: for a profile linear in contact
    # index it is pinned to the midpoint exactly. Measured on a known motif at SNR 100,
    # true crossovers of 5.5 / 7.5 / 11.5 / 15.5 / 18.5 were returned with bias
    # +3.98 / +2.17 / -0.01 / -1.92 / -4.75 contacts, a slope of about 0.31 estimated
    # contacts per true contact, and the shift equalled the removed spatial mean.
    #
    # The relative power fraction P(c, f) / sum_k P(k, f) is the other reading of the
    # published convention. It constrains each column to sum to one, so both band
    # profiles have spatial mean 1/C and Delta(c) again sums to zero: measured bias
    # +3.81 / +2.25 / +0.11 / -1.79 / -4.43, indistinguishable from z-scoring. Any
    # normalization that fixes a column's mean or sum carries this defect.
    #
    # Min-max constrains the extremes instead of the mean, leaving the spatial mean of
    # Delta free to encode where the motif actually reverses.
    col_min = np.min(clean_psd, axis=0)
    col_max = np.max(clean_psd, axis=0)
    col_range = col_max - col_min
    col_range[col_range < 1e-12] = 1e-12
    normed_psd = (clean_psd - col_min) / col_range

    # 4. Band profiles
    low_profile = np.mean(normed_psd[:, mask_low], axis=1)
    high_profile = np.mean(normed_psd[:, mask_high], axis=1)

    # Depth profiles rescaled to [0, 1] across contacts, used only to locate the
    # crossover. The two analysis bands contain different fractions of bins that carry
    # motif power -- with a gamma source at 75 Hz in a 50-150 Hz band and a beta source
    # at 18 Hz in an 8-30 Hz band, about 30% against about 45% -- so each band mean
    # carries its own additive background level. Their difference is then not zero where
    # the motif actually reverses, which displaced the crossing by about +1.9 contacts at
    # a true crossover of 5.5. Rescaling each depth profile to a common range removes the
    # band-specific offset and gain without constraining the spatial mean.
    #
    # The score below deliberately keeps the unscaled profiles: rescaling forces a pure
    # noise profile to span [0, 1] exactly as a real motif does, which is the magnitude
    # evidence the support score exists to weigh.
    low_located = _unit_range(low_profile)
    high_located = _unit_range(high_profile)

    low_peak = int(np.argmax(low_profile))
    high_peak = int(np.argmax(high_profile))

    # 5. Orientation resolution
    if orientation == "auto":
        if high_peak < low_peak:
            resolved_orientation = "superficial_to_deep"
            signed_profile = high_profile - low_profile
            located_profile = high_located - low_located
        elif low_peak < high_peak:
            resolved_orientation = "deep_to_superficial"
            signed_profile = low_profile - high_profile
            located_profile = low_located - high_located
        else:
            resolved_orientation = "undetermined"
            signed_profile = high_profile - low_profile
            located_profile = high_located - low_located
    elif orientation == "superficial_to_deep":
        resolved_orientation = "superficial_to_deep"
        signed_profile = high_profile - low_profile
        located_profile = high_located - low_located
    else:  # deep_to_superficial
        resolved_orientation = "deep_to_superficial"
        signed_profile = low_profile - high_profile
        located_profile = low_located - high_located

    # 6. Orientation consistency check
    orientation_matches = True
    if orientation == "superficial_to_deep" and high_peak >= low_peak:
        orientation_matches = False
    elif orientation == "deep_to_superficial" and low_peak >= high_peak:
        orientation_matches = False
    elif orientation == "auto" and low_peak == high_peak:
        orientation_matches = False

    # 7. Crossover zero-crossing search
    # In resolved coordinate frame: superficial peak is at lower index, deep peak at higher index
    c_sup = min(high_peak, low_peak)
    c_deep = max(high_peak, low_peak)
    peak_sep = c_deep - c_sup

    crossover_c: Optional[float] = None
    crossover_z: Optional[float] = None

    if orientation_matches and peak_sep >= min_peak_distance:
        # Search for zero-crossings between c_sup and c_deep
        # Signed profile: positive at c_sup, negative at c_deep
        cross_candidates = []
        for i in range(c_sup, c_deep):
            v1 = located_profile[i]
            v2 = located_profile[i + 1]
            if (v1 > 0 and v2 <= 0) or (v1 >= 0 and v2 < 0):
                denom = v1 - v2
                sub_c = float(i + (v1 / denom))
                # Keep within interval
                sub_c = min(float(i + 1), max(float(i), sub_c))
                steepness = v1 - v2
                cross_candidates.append((sub_c, steepness))

        if cross_candidates:
            # Select candidate maximizing transition steepness
            cross_candidates.sort(key=lambda x: x[1], reverse=True)
            crossover_c = cross_candidates[0][0]
            if probe_geometry is not None and order is not None:
                sorted_z = probe_geometry.contact_positions[order, 2]
                if np.ptp(sorted_z) > 1e-6:
                    crossover_z = float(np.interp(crossover_c, np.arange(n_channels), sorted_z))
                elif effective_spacing is not None:
                    crossover_z = float(crossover_c * effective_spacing)
            elif effective_spacing is not None:
                crossover_z = float(crossover_c * effective_spacing)

    # 8. Support Score (Omega) Formulation
    # Density-normalized to eliminate systematic channel-count scaling (EXT-REV-003).
    # Uses canonical 24-contact reference baseline (N_ref = 24):
    # - band_dist is normalized by sqrt(n_channels / 24) (RMS profile scaling)
    # - sep_metric is normalized by (n_channels / 24) (fractional span scaling)
    n_ref = 24.0
    density_scale = float((n_channels / n_ref) ** 1.5)

    # Frequency-grid normalization. Under the null each normalized bin is O(1), so a
    # Euclidean norm taken over the whole grid grows as sqrt(n_freqs), while a band mean
    # over n bins has null scale 1/sqrt(n). The score multiplies one of the former by two
    # of the latter, giving a null that falls as n_freqs^(-1/2); in log terms the null
    # median shifts by -0.5 * ln(n_freqs), which reproduced the measured shift across the
    # 126 -> 1001 bin sweep to within 0.27 (exactly at the largest grid). A fixed
    # threshold therefore meant different false-positive rates at different recording
    # lengths and nperseg. Taking the spectral distance as an RMS over bins, and
    # restoring unit null scale to the band-mean terms, makes every factor grid-free.
    # Null variance of H(c) - L(c) is (1/n_high + 1/n_low) times the per-bin variance.
    band_bin_scale = float(np.sqrt(1.0 / (1.0 / max(1, n_high_bins) + 1.0 / max(1, n_low_bins))))

    # 1. Spectral pole distance between low-peak and high-peak contact, as an RMS across
    #    the standardized frequency grid rather than a sum-norm over it
    p_dist = float(
        np.linalg.norm(normed_psd[high_peak] - normed_psd[low_peak]) / np.sqrt(max(1, n_freqs))
    )
    # 2. Band difference profile Euclidean distance across contacts, at unit null scale
    band_dist = float(np.linalg.norm(signed_profile) * band_bin_scale)
    # 3. Contrast magnitude across poles:
    # High-frequency dominance at high peak + Low-frequency dominance at low peak
    contrast = float(
        (
            (high_profile[high_peak] - low_profile[high_peak])
            + (low_profile[low_peak] - high_profile[low_peak])
        )
        * band_bin_scale
    )
    # 4. Spatial separation in channels
    sep_metric = float(max(1, peak_sep))

    metric = (p_dist * band_dist * max(1e-4, contrast) * sep_metric) / density_scale
    support_score = float(np.log(max(1e-12, metric)))

    # 9. Acceptance determination
    accepted = True
    rejection_reason = None

    if not orientation_matches:
        accepted = False
        rejection_reason = "orientation_mismatch"
    elif peak_sep < min_peak_distance:
        accepted = False
        rejection_reason = "insufficient_peak_distance"
    elif crossover_c is None or not (c_sup < crossover_c < c_deep):
        accepted = False
        rejection_reason = "no_crossover"
    elif support_score < min_support_score:
        accepted = False
        rejection_reason = "insufficient_support"

    # Enforce failure invariants: rejected fit implies None crossover
    final_cross_c = crossover_c if accepted else None
    final_cross_z = crossover_z if accepted else None

    return VFlipResult(
        crossover_contact=final_cross_c,
        crossover_depth_um=final_cross_z,
        support_score=support_score,
        profile=located_profile,
        low_peak_contact=low_peak,
        high_peak_contact=high_peak,
        orientation=resolved_orientation,
        accepted=accepted,
        rejection_reason=rejection_reason,
        n_channels=n_channels,
        n_missing=n_missing,
        bad_channel_mask=effective_bad_input,
    )


def vflip_from_lfp(
    lfp: np.ndarray,
    fs: float,
    *,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: Union[str, bool] = "constant",
    scaling: str = "density",
    band_low: Tuple[float, float] = CANONICAL_VFLIP_BANDS["low"],
    band_high: Tuple[float, float] = CANONICAL_VFLIP_BANDS["high"],
    contact_spacing: Optional[float] = None,
    probe_geometry: Optional[Any] = None,
    orientation: str = "auto",
    min_support_score: float = 3.75,
    bad_channel_mask: Optional[np.ndarray] = None,
    min_channels: int = 8,
    min_peak_distance: int = 2,
    device: str = "cpu",
) -> VFlipResult:
    """Vectorized Frequency-based Laminar Identity Profile from raw LFP time series.

    Strict composition:
    1. Computes power spectral density (PSD) per channel from the multi-channel LFP time
       series using Welch's modified periodogram method (:func:`scipy.signal.welch`).
    2. Passes the resulting PSD matrix and explicit frequency coordinates directly to
       :func:`vflip`.

    The identity invariant holds:
    ``vflip_from_lfp(lfp, fs, ...) == vflip(psd, freqs, ...)``
    where ``freqs, psd = scipy.signal.welch(lfp, fs=fs, axis=1, ...)``.

    Args:
        lfp: 2D array of LFP voltage time series with shape `(n_channels, n_times)`.
            Must contain at least two dimensions and finite numeric data.
        fs: Sampling rate of the LFP time series in Hertz (Hz). Must be strictly positive and finite.
        nperseg: Length of each segment for Welch's PSD estimator (default: `min(n_times, int(fs))`,
            yielding a nominal ~1 Hz frequency resolution).
        noverlap: Number of points to overlap between segments (default: `nperseg // 2`).
        window: Window specification for periodogram calculation (default: `'hann'`).
        detrend: Specifies how to detrend each segment (default: `'constant'`).
        scaling: Selects between computing power spectral density (`'density'`) and
            power spectrum (`'spectrum'`). Default: `'density'`.
        band_low: Frequency range (f_min, f_max) in Hz for the low-frequency band (default: 8-30 Hz).
        band_high: Frequency range (f_min, f_max) in Hz for the high-frequency band (default: 50-150 Hz).
        contact_spacing: Inter-contact spacing (pitch) in micrometers (um).
        probe_geometry: Optional :class:`jnwb.ProbeGeometry` object validating probe linearity and
            contact ordering along the shaft.
        orientation: Expected shaft orientation relative to channel indexing:
            - ``"auto"``: Automatically evaluates peak ordering and resolves orientation.
            - ``"superficial_to_deep"``: Requires contact 0 to be superficial (gamma peaks before alpha/beta).
            - ``"deep_to_superficial"``: Requires contact 0 to be deep (alpha/beta peaks before gamma).
        min_support_score: Minimum support score Omega required to accept the fit (default: 3.75).
            Must be a finite float; no sentinels (e.g. -inf) may bypass acceptance logic.
        bad_channel_mask: Optional boolean mask of shape `(n_channels,)` flagging invalid/detached contacts.
            A channel with any NaN or Inf sample is also treated as bad: it is excluded,
            interpolated along depth like a masked contact, and counted in
            ``VFlipResult.n_missing``.
        min_channels: Minimum number of valid channels required along the shaft (default: 8).
        min_peak_distance: Minimum channel distance required between low and high power peaks (default: 2).
        device: Hardware device (`"cpu"` or `"cuda"`).

    Returns:
        :class:`VFlipResult` containing the estimated crossover contact, depth, support score,
        and diagnostic flags.

    Raises:
        ValueError: If `lfp` is not 2D, `fs` is non-positive or non-finite, or parameters
            violate geometry, frequency, or numerical invariants.

    References:
        Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
        potential power across the primate cortex. Nature Neuroscience.
        doi:10.1038/s41593-023-01554-7
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
    """
    # 1. Validate inputs
    fs = float(fs)
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive and finite (Hz), got {fs}")

    lfp_arr = np.asarray(lfp, dtype=np.float64)
    if lfp_arr.ndim != 2:
        raise ValueError(f"lfp must be a 2D array of shape (n_channels, n_times), got ndim={lfp_arr.ndim}")

    n_channels, n_times = lfp_arr.shape
    if n_times == 0:
        raise ValueError("lfp has zero time samples")

    # 2. Welch segment parameters
    eff_nperseg = int(min(n_times, int(fs))) if nperseg is None else int(nperseg)
    if eff_nperseg <= 0 or eff_nperseg > n_times:
        raise ValueError(f"nperseg must be in range [1, {n_times}], got {eff_nperseg}")

    eff_noverlap = (eff_nperseg // 2) if noverlap is None else int(noverlap)
    if eff_noverlap < 0 or eff_noverlap >= eff_nperseg:
        raise ValueError(f"noverlap must be in range [0, {eff_nperseg - 1}], got {eff_noverlap}")

    # 3. Bad channels handling before FFT:
    # If a channel has NaNs or is masked, replace with zeros for welch computation,
    # then restore bad rows to NaN so vflip's missing-contact interpolation handles them.
    if bad_channel_mask is not None:
        initial_bad = np.asarray(bad_channel_mask, dtype=bool).ravel()
        if len(initial_bad) != n_channels:
            raise ValueError(f"bad_channel_mask length ({len(initial_bad)}) != n_channels ({n_channels})")
    else:
        initial_bad = np.zeros(n_channels, dtype=bool)

    non_finite_rows = ~np.all(np.isfinite(lfp_arr), axis=1)
    effective_bad = initial_bad | non_finite_rows

    clean_lfp = lfp_arr.copy()
    if np.any(effective_bad):
        clean_lfp[effective_bad, :] = 0.0

    # 4. Compute Welch PSD across time (axis 1)
    freqs, psd = signal.welch(
        clean_lfp,
        fs=fs,
        window=window,
        nperseg=eff_nperseg,
        noverlap=eff_noverlap,
        detrend=detrend,
        scaling=scaling,
        axis=1,
    )

    # Re-mask bad channels with NaN to ensure vflip processes them as missing
    if np.any(effective_bad):
        psd[effective_bad, :] = np.nan

    # 5. Strict composition with vflip
    return vflip(
        psd,
        freqs,
        band_low=band_low,
        band_high=band_high,
        contact_spacing=contact_spacing,
        probe_geometry=probe_geometry,
        orientation=orientation,
        min_support_score=min_support_score,
        bad_channel_mask=effective_bad,
        min_channels=min_channels,
        min_peak_distance=min_peak_distance,
        device=device,
    )


def label_layers(
    vflip_result: VFlipResult,
    probe_geometry: Any,
    *,
    granular_thickness_um: float = 400.0,
    bad_channel_mask: Optional[np.ndarray] = None,
    depth_range_um: Optional[Tuple[float, float]] = None,
    contact_range: Optional[Tuple[float, float]] = None,
) -> Dict[Any, str]:
    """Assign cortical layer labels (superficial, input, deep) to probe contacts.

    Maps contacts along a linear probe shaft into canonical cortical compartments:
    - ``"superficial"``: Supragranular layers (L1–L3), characterized by gamma dominance.
    - ``"input"``: Granular layer 4 (L4), centered at the spectrolaminar crossover point,
      extending across a zone of width `granular_thickness_um`.
    - ``"deep"``: Infragranular layers (L5–L6), characterized by alpha/beta dominance.
    - ``"na"``: Assigned to all channels whenever `vflip_result.accepted` is `False`, or to
      invalid, bad, or out-of-bounds contacts.

    Critical Invariant:
    Rejected or non-identifiable fits (`vflip_result.accepted is False`) strictly map
    **all** channels to ``"na"``. Never guesses or imputes layers on failed fits. On accepted
    fits, bad contacts (from `bad_channel_mask` or `vflip_result.bad_channel_mask`), contacts
    with non-finite coordinates, and contacts outside `depth_range_um` or `contact_range`
    strictly receive ``"na"``.

    Args:
        vflip_result: :class:`VFlipResult` container from :func:`vflip` or :func:`vflip_from_lfp`.
        probe_geometry: :class:`jnwb.ProbeGeometry` describing the physical contact positions
            and ordering along the linear probe shaft. Must satisfy `is_linear=True`.
        granular_thickness_um: Thickness of the granular layer (input zone) in micrometers (um).
            Must be strictly positive and finite (default: 400.0 um).
        bad_channel_mask: Optional boolean array matching `probe_geometry.channel_ids`. Contacts
            flagged True receive ``"na"``. If omitted, defaults to `vflip_result.bad_channel_mask`.
        depth_range_um: Optional (min_depth_um, max_depth_um) tuple bounding valid cortical depth
            along the shaft. Contacts outside this range receive ``"na"``.
        contact_range: Optional (min_contact, max_contact) tuple bounding valid contact indices
            along the ordered linear shaft. Contacts outside this range receive ``"na"``.

    Returns:
        Dictionary mapping channel identifier (from `probe_geometry.channel_ids`) to layer label
        string: ``"superficial"``, ``"input"``, ``"deep"``, or ``"na"``.

    Raises:
        ValueError: If `granular_thickness_um` is non-positive or non-finite, `probe_geometry`
            is not linear, channel count does not match `vflip_result.n_channels`, or range bounds
            are invalid.

    References:
        Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
        potential power across the primate cortex. Nature Neuroscience.
        doi:10.1038/s41593-023-01554-7
    """
    # 1. Parameter validation
    granular_thickness_um = float(granular_thickness_um)
    if granular_thickness_um <= 0 or not np.isfinite(granular_thickness_um):
        raise ValueError(
            f"granular_thickness_um must be strictly positive and finite (um), got {granular_thickness_um}"
        )

    if depth_range_um is not None:
        if len(depth_range_um) != 2:
            raise ValueError(f"depth_range_um must be a 2-tuple (min_depth, max_depth), got {depth_range_um}")
        min_d, max_d = float(depth_range_um[0]), float(depth_range_um[1])
        if min_d > max_d or not (np.isfinite(min_d) and np.isfinite(max_d)):
            raise ValueError(f"depth_range_um bounds must be finite with min <= max, got {depth_range_um}")

    if contact_range is not None:
        if len(contact_range) != 2:
            raise ValueError(f"contact_range must be a 2-tuple (min_contact, max_contact), got {contact_range}")
        min_c, max_c = float(contact_range[0]), float(contact_range[1])
        if min_c > max_c or not (np.isfinite(min_c) and np.isfinite(max_c)):
            raise ValueError(f"contact_range bounds must be finite with min <= max, got {contact_range}")

    if probe_geometry is None or not getattr(probe_geometry, "is_linear", False):
        raise ValueError("probe_geometry must describe a linear electrode shaft (is_linear=True)")

    channel_ids = list(probe_geometry.channel_ids)
    n_geom_channels = len(channel_ids)
    if n_geom_channels != vflip_result.n_channels:
        raise ValueError(
            f"probe_geometry channel count ({n_geom_channels}) does not match "
            f"vflip_result.n_channels ({vflip_result.n_channels})"
        )

    # 2. Strict rejection invariant: unaccepted fits yield all "na"
    if not vflip_result.accepted or vflip_result.crossover_contact is None:
        return {ch_id: "na" for ch_id in channel_ids}

    # 3. Determine contact positions along shaft
    nominal_pitch = getattr(probe_geometry, "nominal_pitch", None)
    if nominal_pitch is None or nominal_pitch <= 0:
        raise ValueError(
            "probe_geometry.nominal_pitch must be strictly positive to compute layer boundaries in um"
        )
    pitch = float(nominal_pitch)

    # Resolve bad channel mask
    if bad_channel_mask is not None:
        effective_bad = np.asarray(bad_channel_mask, dtype=bool).ravel()
        if len(effective_bad) != n_geom_channels:
            raise ValueError(
                f"bad_channel_mask length ({len(effective_bad)}) does not match "
                f"probe_geometry channel count ({n_geom_channels})"
            )
    else:
        res_bad = getattr(vflip_result, "bad_channel_mask", None)
        if res_bad is not None and len(res_bad) == n_geom_channels:
            effective_bad = np.asarray(res_bad, dtype=bool).ravel()
        else:
            effective_bad = None

    # Number of channels spanning granular layer
    mid_half_span = (granular_thickness_um / 2.0) / pitch
    crossover = float(vflip_result.crossover_contact)

    # Granular (input) boundary interval in contact coordinate space
    input_start = crossover - mid_half_span
    input_end = crossover + mid_half_span

    # Orientation mapping:
    # Under 'superficial_to_deep': lower contact indices are superficial, higher are deep.
    # Under 'deep_to_superficial': lower contact indices are deep, higher are superficial.
    is_sup_to_deep = (vflip_result.orientation == "superficial_to_deep")

    # Map each channel in channel_ids to its position index along the ordered linear shaft
    order = getattr(probe_geometry, "linear_order", None)
    if order is not None and len(order) == n_geom_channels:
        rank = np.empty(n_geom_channels, dtype=float)
        rank[order] = np.arange(n_geom_channels, dtype=float)
    else:
        rank = np.arange(n_geom_channels, dtype=float)

    labels: Dict[Any, str] = {}
    has_positions = hasattr(probe_geometry, "contact_positions") and probe_geometry.contact_positions is not None

    for idx, ch_id in enumerate(channel_ids):
        # Bad / masked channel exclusion
        if effective_bad is not None and effective_bad[idx]:
            labels[ch_id] = "na"
            continue

        # Contact geometry validity check
        if has_positions:
            pos = probe_geometry.contact_positions[idx]
            if not np.all(np.isfinite(pos)):
                labels[ch_id] = "na"
                continue

        c_pos = float(rank[idx])

        # Shaft support bounds
        if c_pos < 0 or c_pos >= n_geom_channels:
            labels[ch_id] = "na"
            continue

        # Contact index range check
        if contact_range is not None:
            if not (min_c <= c_pos <= max_c):
                labels[ch_id] = "na"
                continue

        # Physical depth range check
        if depth_range_um is not None:
            c_depth = c_pos * pitch
            if not (min_d <= c_depth <= max_d):
                labels[ch_id] = "na"
                continue

        # In-bounds cortical layer assignment
        if input_start <= c_pos <= input_end:
            labels[ch_id] = "input"
        elif c_pos < input_start:
            labels[ch_id] = "superficial" if is_sup_to_deep else "deep"
        else:  # c_pos > input_end
            labels[ch_id] = "deep" if is_sup_to_deep else "superficial"

    return labels


@dataclass(frozen=True)
class XFlipResult(DictAccessMixin):
    """Container for Cross-Channel Laminar Correlation Profile (xFLIP) results.

    Attributes:
        corr_matrix: 2D array of shape (n_channels, n_channels) containing the
            computed or supplied inter-channel correlation matrix.
        block_bounds: Tuple of half-open integer index intervals (start, end)
            defining each contiguous contact block along the probe shaft.
        boundaries: Tuple of integer contact indices where block boundaries occur.
        labels: 1D integer array of shape (n_channels,) with block membership (0, 1, ...).
        modularity: Observed modularity/contrast score Q = mean(within) - mean(between).
        p_values: Dict mapping test names to Monte Carlo p-values ('omnibus' and per-boundary).
        accepted: Boolean flag indicating whether the block partition is statistically
            significant (p <= alpha) and satisfies all structural constraints.
        rejection_reason: Diagnostic reason string if rejected, or None if accepted.
        method: Correlation method used ('pearson', 'spearman', 'partial', or 'precomputed').
        n_channels: Number of channels evaluated.
        n_blocks: Number of detected blocks.
        boundary_drops: Optional dict mapping each interior boundary index to its
            local correlation drop (within-block neighbor correlation minus cross-boundary correlation).
    """

    corr_matrix: np.ndarray
    block_bounds: Tuple[Tuple[int, int], ...]
    boundaries: Tuple[int, ...]
    labels: np.ndarray
    modularity: float
    p_values: Dict[str, float]
    accepted: bool
    rejection_reason: Optional[str]
    method: str
    n_channels: int
    n_blocks: int
    boundary_drops: Optional[Dict[int, float]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "corr_matrix": self.corr_matrix.copy(),
            "block_bounds": self.block_bounds,
            "boundaries": self.boundaries,
            "labels": self.labels.copy(),
            "modularity": float(self.modularity),
            "p_values": dict(self.p_values),
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "method": str(self.method),
            "n_channels": int(self.n_channels),
            "n_blocks": int(self.n_blocks),
            "boundary_drops": dict(self.boundary_drops) if self.boundary_drops is not None else {},
        }


def _compute_correlation_matrix(data: np.ndarray, method: str) -> np.ndarray:
    """Compute (n_channels, n_channels) correlation matrix across samples.

    Args:
        data: 2D array of shape (n_channels, n_samples).
        method: 'pearson', 'spearman', or 'partial'.
    """
    n_channels, n_samples = data.shape
    if method == "pearson":
        corr = np.corrcoef(data)
        if np.any(np.isnan(corr)):
            np.nan_to_num(corr, copy=False, nan=0.0)
            np.fill_diagonal(corr, 1.0)
        return np.clip(corr, -1.0, 1.0)

    elif method == "spearman":
        ranks = rankdata(data, axis=1)
        corr = np.corrcoef(ranks)
        if np.any(np.isnan(corr)):
            np.nan_to_num(corr, copy=False, nan=0.0)
            np.fill_diagonal(corr, 1.0)
        return np.clip(corr, -1.0, 1.0)

    elif method == "partial":
        cov = np.cov(data)
        if np.allclose(cov, 0.0):
            return np.eye(n_channels, dtype=float)
        try:
            cond = np.linalg.cond(cov)
            if cond > 1e12 or not np.isfinite(cond):
                theta = np.linalg.pinv(cov)
            else:
                theta = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            theta = np.linalg.pinv(cov)

        d = np.diag(theta)
        d_pos = np.maximum(d, 1e-12)
        denom = np.sqrt(np.outer(d_pos, d_pos))
        p_corr = -theta / denom
        np.fill_diagonal(p_corr, 1.0)
        return np.clip(p_corr, -1.0, 1.0)

    raise ValueError(f"Unknown correlation method '{method}'")


def _surrogate_phase_randomize(data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Fourier phase randomization independently per channel.

    Preserves each channel's empirical power spectral density and temporal
    autocorrelation R_{cc}(tau) while destroying cross-channel phase coherence.
    """
    n_channels, n_samples = data.shape
    fft_coeffs = np.fft.rfft(data, axis=1)
    magnitudes = np.abs(fft_coeffs)
    n_freqs = fft_coeffs.shape[1]

    rand_phases = rng.uniform(0.0, 2.0 * np.pi, size=(n_channels, n_freqs))
    rand_phases[:, 0] = 0.0
    if n_samples % 2 == 0:
        rand_phases[:, -1] = 0.0

    surrogate_fft = magnitudes * np.exp(1j * rand_phases)
    return np.fft.irfft(surrogate_fft, n=n_samples, axis=1)


def _compute_contrast(corr: np.ndarray, labels: np.ndarray) -> float:
    """Compute block contrast Q = mean(within) - mean(between)."""
    n = corr.shape[0]
    triu_r, triu_c = np.triu_indices(n, k=1)
    if len(triu_r) == 0:
        return 0.0
    vals = corr[triu_r, triu_c]
    same_label = (labels[triu_r] == labels[triu_c])
    within_cnt = int(np.sum(same_label))
    between_cnt = int(np.sum(~same_label))

    mean_within = float(np.sum(vals[same_label]) / within_cnt) if within_cnt > 0 else 0.0
    mean_between = float(np.sum(vals[~same_label]) / between_cnt) if between_cnt > 0 else 0.0
    return mean_within - mean_between


def _optimal_contiguous_partition(
    corr: np.ndarray,
    n_blocks: int,
    min_block_size: int,
) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...], float, np.ndarray]:
    """Find globally optimal contiguous partition using 1D dynamic programming.

    Maximizes modularity sum: W(u, v) = S(u, v) - gamma * P(u, v),
    where S(u, v) is sum of off-diagonal correlations in [u, v),
    P(u, v) is number of pairs (v-u)*(v-u-1)/2,
    and gamma is the probe-wide mean off-diagonal correlation.

    Returns:
        (block_bounds, boundaries, modularity, labels)
    """
    n = corr.shape[0]
    if n_blocks == 1:
        labels = np.zeros(n, dtype=int)
        return ((0, n),), (), 0.0, labels

    triu_idx = np.triu_indices(n, k=1)
    gamma = float(np.mean(corr[triu_idx])) if len(triu_idx[0]) > 0 else 0.0

    prefix = np.zeros((n + 1, n + 1), dtype=float)
    prefix[1:, 1:] = np.cumsum(np.cumsum(corr, axis=0), axis=1)
    # 05-47: the off-diagonal term below was already answered from `prefix` in constant
    # time while the diagonal term re-summed a slice on every call. `np.diag` returns a
    # view, so nothing was copied, but the call plus the slice plus the reduction cost
    # 4.82 of the 5.56 microseconds an `interval_w` call took -- 87% of it -- and the DP
    # makes about 93000 of them at n=256 with n_blocks=4, once per surrogate. Prefix-
    # summing the diagonal answers it the way the off-diagonal term is already answered.
    #
    # This is not bit-identical to re-summing: a difference of two running totals is a
    # different floating-point operation from a pairwise reduction, and on a real
    # correlation matrix -- whose diagonal `np.corrcoef` does not always make exactly
    # 1.0 -- the two disagree by up to 4e-15. It cannot reach the answer. For a fixed
    # (k, j) every candidate partition tiles [0, j), so the per-block diagonal terms sum
    # to `f(j) - f(0)` whatever the cuts are: the same constant in every candidate,
    # cancelling out of the comparison. The returned modularity is computed separately
    # by `_compute_contrast` from the labels, and never sees `dp` at all.
    diag_cum = np.concatenate(([0.0], np.cumsum(np.diag(corr))))

    def interval_w(u: int, v: int) -> float:
        sz = v - u
        if sz < min_block_size:
            return -np.inf
        total_sub = prefix[v, v] - prefix[u, v] - prefix[v, u] + prefix[u, u]
        diag_sub = diag_cum[v] - diag_cum[u]
        s_uv = 0.5 * (total_sub - diag_sub)
        p_uv = 0.5 * sz * (sz - 1)
        return float(s_uv - gamma * p_uv)

    dp = np.full((n_blocks + 1, n + 1), -np.inf, dtype=float)
    parent = np.full((n_blocks + 1, n + 1), -1, dtype=int)

    for j in range(min_block_size, n + 1):
        dp[1, j] = interval_w(0, j)

    for k in range(2, n_blocks + 1):
        min_j = k * min_block_size
        for j in range(min_j, n + 1):
            best_val = -np.inf
            best_u = -1
            for u in range((k - 1) * min_block_size, j - min_block_size + 1):
                if dp[k - 1, u] == -np.inf:
                    continue
                w = interval_w(u, j)
                if w == -np.inf:
                    continue
                val = dp[k - 1, u] + w
                if val > best_val:
                    best_val = val
                    best_u = u
            dp[k, j] = best_val
            parent[k, j] = best_u

    if dp[n_blocks, n] == -np.inf:
        labels = np.zeros(n, dtype=int)
        return ((0, n),), (), 0.0, labels

    cuts = []
    curr_j = n
    for k in range(n_blocks, 1, -1):
        u = parent[k, curr_j]
        cuts.append(u)
        curr_j = u
    cuts.reverse()

    boundaries = tuple(cuts)
    all_cuts = [0] + list(boundaries) + [n]
    block_bounds = tuple((all_cuts[i], all_cuts[i + 1]) for i in range(len(all_cuts) - 1))

    labels = np.zeros(n, dtype=int)
    for b_idx, (st, en) in enumerate(block_bounds):
        labels[st:en] = b_idx

    modularity = _compute_contrast(corr, labels)
    return block_bounds, boundaries, modularity, labels


def _label_change_boundaries(labels: np.ndarray) -> Tuple[int, ...]:
    """Positions along the probe where the cluster label changes."""
    return tuple(int(i) for i in range(1, len(labels)) if labels[i] != labels[i - 1])


def _partition_is_contiguous(labels: np.ndarray) -> bool:
    """Does every cluster occupy one unbroken span of the channel index?"""
    n_clusters = int(np.unique(labels).size)
    return len(_label_change_boundaries(labels)) == max(n_clusters - 1, 0)


def _unrestricted_partition(
    corr: np.ndarray,
    n_blocks: int,
) -> Tuple[Tuple[Tuple[int, int], ...], Tuple[int, ...], float, np.ndarray]:
    """Unrestricted agglomerative clustering on correlation distance matrix."""
    n = corr.shape[0]
    if n_blocks <= 1:
        labels = np.zeros(n, dtype=int)
        return ((0, n),), (), 0.0, labels

    d = np.clip(1.0 - corr, 0.0, 2.0)
    np.fill_diagonal(d, 0.0)
    d = 0.5 * (d + d.T)
    condensed_d = squareform(d, checks=False)
    z = linkage(condensed_d, method="average")
    raw_labels = fcluster(z, t=n_blocks, criterion="maxclust") - 1

    unique_labels: List[int] = []
    for lbl in raw_labels:
        if lbl not in unique_labels:
            unique_labels.append(lbl)
    remap = {old: new for new, old in enumerate(unique_labels)}
    labels = np.array([remap[lbl] for lbl in raw_labels], dtype=int)

    bounds = []
    for k in range(len(unique_labels)):
        members = np.where(labels == k)[0]
        if len(members) > 0:
            bounds.append((int(np.min(members)), int(np.max(members) + 1)))

    modularity = _compute_contrast(corr, labels)
    return tuple(bounds), (), modularity, labels


def xflip(
    data: np.ndarray,
    *,
    method: str = "pearson",
    contiguous: bool = True,
    n_blocks: Optional[int] = 2,
    min_block_size: int = 2,
    n_surrogates: int = 200,
    surrogate_method: str = "auto",
    alpha: float = 0.05,
    min_contrast: float = 0.05,
    min_boundary_drop: float = 0.05,
    channel_axis: int = 0,
    is_corr_matrix: Optional[bool] = None,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> XFlipResult:
    """Cross-Channel Laminar Correlation Profile (xFLIP).

    Evaluates cross-channel correlation blocks along laminar electrode array shafts,
    partitions contacts into contiguous laminar compartments via exact 1D dynamic
    programming, and tests boundary significance against temporal autocorrelation-preserving
    Fourier phase surrogates.

    Mathematical Estimator:
        1. Correlation Estimation:
           - Pearson: standard sample correlation across observations:
             :math:`r_{ij} = \\frac{\\sum_t (X_{it} - \\bar{X}_i)(X_{jt} - \\bar{X}_j)}{\\sigma_i \\sigma_j}`.
           - Spearman: rank-transformed sample correlation.
           - Partial: inverse covariance (precision) matrix normalization:
             :math:`r_{ij|\\text{rest}} = -\\frac{\\Theta_{ij}}{\\sqrt{\\Theta_{ii}\\Theta_{jj}}}`.
           - Precomputed: validates symmetry, unit diagonal, and bounds [-1, 1].
        2. Optimal Contiguous Partitioning:
           When `contiguous=True`, computes the globally optimal segmentation into `n_blocks`
           contiguous intervals :math:`[b_{k-1}, b_k)` via 1D dynamic programming maximizing
           the modularity contrast over the probe-wide baseline :math:`\\gamma = \\bar{R}`:
           :math:`W(u, v) = \\sum_{u \\le i < j < v} (R_{ij} - \\gamma)`.
        3. Statistical Null Testing:
           Constructs surrogates preserving each channel's empirical power spectrum and
           temporal autocorrelation :math:`R_{cc}(\\tau)` via independent Fourier phase
           randomization (when raw time-series data is provided), or channel identity permutation
           (when a precomputed correlation matrix is provided).
        4. Monte Carlo P-value Resolution:
           Evaluates partition contrast :math:`Q = \\bar{r}_{\\text{within}} - \\bar{r}_{\\text{between}}`:
           :math:`p = \\frac{1 + \\sum_{s=1}^S \\mathbb{I}(Q_s \\ge Q)}{1 + S}`.
           No p-value can resolve to 0.0 under finite surrogate sampling.

    Args:
        data: 2D array of raw time series `(n_channels, n_samples)` or precomputed
            correlation matrix `(n_channels, n_channels)`.
        method: Correlation method for raw time series: `'pearson'`, `'spearman'`,
            or `'partial'` (default: `'pearson'`).
        contiguous: If True, partitions into contiguous contact segments along the probe
            shaft (default: True). If False, performs unrestricted clustering.
        n_blocks: Number of blocks to partition into, or None to evaluate over 2..K (default: 2).
        min_block_size: Minimum channel count required per block (default: 2).
        n_surrogates: Number of Monte Carlo surrogate iterations (default: 200). If 0,
            surrogate p-values are not computed (NaN) and the result is never accepted:
            not testing is not the same as passing, and `rejection_reason` says so.
        surrogate_method: `'auto'` (default), `'autocorr_preserving'`, or `'permute_channels'`.
        alpha: Significance threshold for omnibus surrogate test (default: 0.05).
        min_contrast: Minimum modularity contrast required for acceptance (default: 0.05).
        min_boundary_drop: Minimum drop between within-block neighbor correlations and cross-boundary
            correlation required for boundary acceptance (default: 0.05). Guards against false
            partitioning of continuous smooth spatial gradients without sharp boundaries.
        channel_axis: Axis corresponding to channels in raw time-series input (default: 0).
        is_corr_matrix: Explicit boolean override specifying whether `data` is a precomputed
            correlation matrix. If None, auto-detected from shape, symmetry, and values.
        rng: Optional NumPy Generator or integer seed for surrogate reproducibility.

    Returns:
        XFlipResult container with `block_bounds`, `boundaries`, `labels`, `modularity`,
        `p_values`, `accepted`, and `rejection_reason`.

    Raises:
        ValueError: If data is non-2D, non-finite, ill-conditioned/non-symmetric precomputed
            matrix, or contains invalid configuration parameters.
    """
    if method not in ("pearson", "spearman", "partial"):
        raise ValueError(
            f"Unknown correlation method '{method}'. Supported methods: 'pearson', 'spearman', 'partial'."
        )
    if min_block_size < 1:
        raise ValueError(f"min_block_size must be >= 1, got {min_block_size}")
    if n_blocks is not None and n_blocks < 1:
        raise ValueError(f"n_blocks must be >= 1, got {n_blocks}")
    if n_surrogates < 0:
        raise ValueError(f"n_surrogates must be >= 0, got {n_surrogates}")
    # `is_sig = p <= alpha` is vacuously true for alpha >= 1, and the two thresholds were
    # equally unchecked: alpha=5.0 with min_boundary_drop=0.0 accepted a smooth spatial
    # gradient in 15 of 15 seeds. `zflip` already range-checks the identical parameter.
    if not (np.isfinite(alpha) and 0.0 < alpha < 1.0):
        raise ValueError(f"alpha must lie in (0, 1); got {alpha}.")
    if not (np.isfinite(min_contrast) and min_contrast >= 0.0):
        raise ValueError(f"min_contrast must be a finite value >= 0; got {min_contrast}.")
    if not (np.isfinite(min_boundary_drop) and min_boundary_drop >= 0.0):
        raise ValueError(
            f"min_boundary_drop must be a finite value >= 0; got {min_boundary_drop}."
        )
    if min_block_size < 1:
        raise ValueError(f"min_block_size must be >= 1, got {min_block_size}")

    arr = np.asarray(data)
    if arr.ndim != 2:
        raise ValueError(f"data must be a 2D array, got shape {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("Input data contains non-finite values (NaN or Inf).")

    # Determine whether input is a precomputed correlation matrix
    if is_corr_matrix is True:
        if arr.shape[0] != arr.shape[1]:
            raise ValueError(f"is_corr_matrix=True requires a square (n_channels, n_channels) matrix, got {arr.shape}")
        if not np.allclose(arr, arr.T, atol=1e-4):
            raise ValueError("Precomputed correlation matrix must be symmetric.")
        if not np.allclose(np.diag(arr), 1.0, atol=1e-3):
            raise ValueError("Precomputed correlation matrix diagonal elements must be 1.0.")
        if np.any(arr < -1.0 - 1e-4) or np.any(arr > 1.0 + 1e-4):
            raise ValueError("Precomputed correlation matrix elements must be in [-1, 1].")
        is_corr = True
    elif is_corr_matrix is False:
        is_corr = False
    else:
        # Auto-detect
        if (
            arr.shape[0] == arr.shape[1]
            and np.allclose(arr, arr.T, atol=1e-4)
            and np.allclose(np.diag(arr), 1.0, atol=1e-3)
            and np.all(arr >= -1.0 - 1e-4)
            and np.all(arr <= 1.0 + 1e-4)
        ):
            is_corr = True
        else:
            is_corr = False

    if not is_corr:
        if channel_axis == 1:
            raw_data = arr.T
        elif channel_axis == 0:
            raw_data = arr
        else:
            raise ValueError(f"channel_axis must be 0 or 1, got {channel_axis}")
        n_channels, n_samples = raw_data.shape
        if n_samples <= 1:
            raise ValueError(f"Raw time-series must have at least 2 samples, got {n_samples}")
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = _compute_correlation_matrix(raw_data, method)
        resolved_method = method
        flat = np.flatnonzero(np.ptp(raw_data, axis=1) == 0)
        if flat.size > 0:
            # A zero-variance channel has no correlation with any other. Its entries were set to
            # 0, "uncorrelated", which the partition search reads as a block boundary.
            corr = corr.copy()
            corr[flat, :] = np.nan
            corr[:, flat] = np.nan
            return XFlipResult(
                corr_matrix=corr,
                block_bounds=((0, n_channels),),
                boundaries=(),
                labels=np.zeros(n_channels, dtype=int),
                modularity=np.nan,
                p_values={"omnibus": np.nan},
                accepted=False,
                rejection_reason=(
                    f"Zero-variance channel(s) {flat.tolist()} have undefined correlation; "
                    "mask or remove them before partitioning."
                ),
                method=resolved_method,
                n_channels=n_channels,
                n_blocks=1,
            )
    else:
        raw_data = None
        corr = np.clip(arr.copy(), -1.0, 1.0)
        n_channels = corr.shape[0]
        resolved_method = "precomputed"

    # Resolve surrogate method
    if surrogate_method == "auto":
        eff_surrogate_method = "autocorr_preserving" if raw_data is not None else "permute_channels"
    elif surrogate_method in ("autocorr_preserving", "phase_randomize"):
        if raw_data is None:
            raise ValueError(
                "surrogate_method='autocorr_preserving' requires raw time-series data to evaluate "
                "temporal autocorrelation; got a precomputed correlation matrix. "
                "Pass raw data or use surrogate_method='permute_channels'."
            )
        eff_surrogate_method = "autocorr_preserving"
    elif surrogate_method in ("permute_channels", "channel_permute"):
        eff_surrogate_method = "permute_channels"
    else:
        raise ValueError(
            f"Unknown surrogate_method '{surrogate_method}'. "
            "Supported: 'auto', 'autocorr_preserving', 'permute_channels'."
        )

    # Check structural feasibility
    target_k = 2 if n_blocks is None else n_blocks
    if n_channels < target_k * min_block_size:
        labels = np.zeros(n_channels, dtype=int)
        return XFlipResult(
            corr_matrix=corr,
            block_bounds=((0, n_channels),),
            boundaries=(),
            labels=labels,
            modularity=0.0,
            p_values={"omnibus": np.nan},
            accepted=False,
            rejection_reason=(
                f"Total channels ({n_channels}) insufficient for {target_k} blocks "
                f"with min_block_size {min_block_size} (requires >= {target_k * min_block_size})."
            ),
            method=resolved_method,
            n_channels=n_channels,
            n_blocks=1,
        )

    # Optimal partition on observed data
    if n_blocks is not None:
        if contiguous:
            b_bounds, boundaries, obs_q, labels = _optimal_contiguous_partition(corr, target_k, min_block_size)
        else:
            b_bounds, boundaries, obs_q, labels = _unrestricted_partition(corr, target_k)
    else:
        max_k = min(4, n_channels // min_block_size)
        best_q = -np.inf
        best_res = None
        target_k = 2
        for k_cand in range(2, max_k + 1):
            if contiguous:
                bb, bnd, q_cand, lbl = _optimal_contiguous_partition(corr, k_cand, min_block_size)
            else:
                bb, bnd, q_cand, lbl = _unrestricted_partition(corr, k_cand)
            if q_cand > best_q:
                best_q = q_cand
                best_res = (bb, bnd, q_cand, lbl)
                target_k = k_cand
        if best_res is not None:
            b_bounds, boundaries, obs_q, labels = best_res
        else:
            b_bounds = ((0, n_channels),)
            boundaries = ()
            obs_q = 0.0
            labels = np.zeros(n_channels, dtype=int)

    # Monte Carlo surrogate null testing
    gen = np.random.default_rng(rng)
    p_values: Dict[str, float] = {}

    if n_surrogates > 0:
        count_exceed = 0
        boundary_exceed = {b: 0 for b in boundaries}

        for _ in range(n_surrogates):
            if eff_surrogate_method == "autocorr_preserving":
                surr_raw = _surrogate_phase_randomize(raw_data, gen)
                surr_corr = _compute_correlation_matrix(surr_raw, method)
            else:
                if contiguous:
                    perm = gen.permutation(n_channels)
                    surr_corr = corr[perm, :][:, perm]
                else:
                    triu_idx = np.triu_indices(n_channels, k=1)
                    perm_vals = gen.permutation(corr[triu_idx])
                    surr_corr = np.eye(n_channels, dtype=float)
                    surr_corr[triu_idx] = perm_vals
                    surr_corr[triu_idx[1], triu_idx[0]] = perm_vals

            if contiguous:
                _, _, surr_q, _ = _optimal_contiguous_partition(surr_corr, target_k, min_block_size)
            else:
                _, _, surr_q, _ = _unrestricted_partition(surr_corr, target_k)

            if surr_q >= obs_q:
                count_exceed += 1

            for b in boundaries:
                left_st = 0
                right_en = n_channels
                for bb_st, bb_en in b_bounds:
                    if bb_en == b:
                        left_st = bb_st
                    elif bb_st == b:
                        right_en = bb_en
                        break

                local_lbl = np.zeros(right_en - left_st, dtype=int)
                local_lbl[b - left_st:] = 1
                local_surr_q = _compute_contrast(surr_corr[left_st:right_en, left_st:right_en], local_lbl)
                local_obs_q = _compute_contrast(corr[left_st:right_en, left_st:right_en], local_lbl)
                if local_surr_q >= local_obs_q:
                    boundary_exceed[b] += 1

        p_omnibus = (1 + count_exceed) / (1 + n_surrogates)
        p_values["omnibus"] = float(p_omnibus)
        for b in boundaries:
            p_values[f"boundary_{b}"] = float((1 + boundary_exceed[b]) / (1 + n_surrogates))
    else:
        p_values["omnibus"] = np.nan

    # Evaluate boundary drops (local discontinuity across candidate cuts)
    # On the unrestricted path the partition carries no boundaries of its own, but a
    # partition that happens to be contiguous has the same cuts the DP would have produced.
    drop_boundaries = boundaries
    if not contiguous and _partition_is_contiguous(labels):
        drop_boundaries = _label_change_boundaries(labels)

    boundary_drops: Dict[int, float] = {}
    if len(drop_boundaries) > 0:
        for b in drop_boundaries:
            within_neighbors = []
            if b >= 2:
                within_neighbors.append(float(corr[b - 2, b - 1]))
            if b < n_channels - 1:
                within_neighbors.append(float(corr[b, b + 1]))
            mean_near = float(np.mean(within_neighbors)) if len(within_neighbors) > 0 else 1.0
            cross_val = float(corr[b - 1, b])
            boundary_drops[b] = float(mean_near - cross_val)

    # Acceptance determination
    # `n_surrogates=0` means the significance test was not performed, which is not the
    # same as passing it. Assuming True here accepted pure noise in 119 of 120 seeds
    # (contrast and boundary-drop gates opened), and the surrogate test would have rejected
    # 113 of those, with omnibus p running as high as 0.87 -- while `p_values['omnibus']`
    # was reported as NaN. `zflip` already documents the opposite contract: accepted only
    # if the surrogate test was performed AND significant. This now matches it.
    surrogates_run = n_surrogates > 0
    is_sig = bool(p_values["omnibus"] <= alpha) if surrogates_run else False
    has_contrast = (obs_q >= min_contrast)
    has_blocks = (target_k >= 2)
    # The gradient gate. It used to run only under `contiguous`, while `has_drop` was
    # initialised True, so the unrestricted path silently *skipped* it rather than failing
    # it -- the same "not tested is not passed" error the `n_surrogates=0` contract above
    # exists to prevent. A smooth spatial gradient was accepted in 15 of 15 seeds there
    # where the contiguous path accepted 0 of 15.
    #
    # The statistic is a *local* discontinuity, and locality is the point: a smooth
    # exponential decay separates perfectly well at the cluster level (within-minus-between
    # is 0.3285 on the gradient null), so only the drop across the cut distinguishes a real
    # boundary from a gradient. It is therefore applied exactly when a gradient could have
    # produced the partition -- that is, when the partition is contiguous. A genuinely
    # interleaved partition cannot come from a spatial gradient, so the gate does not apply
    # and `unrestricted_partition_is_interleaved` records that it did not.
    has_drop = True
    if min_boundary_drop > 0.0 and len(drop_boundaries) > 0:
        for b, drop_val in boundary_drops.items():
            if drop_val < min_boundary_drop:
                has_drop = False
                break

    if is_sig and has_contrast and has_blocks and has_drop:
        accepted = True
        rejection_reason = None
    else:
        accepted = False
        reasons = []
        if not surrogates_run:
            reasons.append(
                "Surrogate significance test not performed (n_surrogates=0); acceptance "
                "requires the test to run"
            )
        elif not is_sig:
            reasons.append(f"Non-significant modularity vs surrogates (p = {p_values['omnibus']:.4f} > {alpha})")
        if not has_contrast:
            reasons.append(f"Modularity contrast ({obs_q:.4f}) below min_contrast ({min_contrast})")
        if not has_blocks:
            reasons.append(f"Fewer than 2 blocks detected (k = {target_k})")
        if not has_drop:
            reasons.append(f"Boundary drop below min_boundary_drop ({min_boundary_drop})")
        rejection_reason = "; ".join(reasons)

    return XFlipResult(
        corr_matrix=corr,
        block_bounds=b_bounds,
        boundaries=boundaries,
        labels=labels,
        modularity=float(obs_q),
        p_values=p_values,
        accepted=accepted,
        rejection_reason=rejection_reason,
        method=resolved_method,
        n_channels=n_channels,
        n_blocks=target_k if accepted else 1,
        boundary_drops=boundary_drops,
    )


@dataclass(frozen=True)
class ZFlipResult(DictAccessMixin):
    """Container for zFLIP Cortical Depth Phase-Gradient & Delay Estimation results.

    zFLIP estimates laminar phase slope and propagation latency across ordered
    electrode contacts along a linear probe shaft.

    Attributes:
        adjacent_wpli: 1D array of shape (n_channels - 1,) containing the weighted
            Phase Lag Index between adjacent contacts; NaN when not computed.
        adjacent_delays_s: 1D array of shape (n_channels - 1,) of pairwise delay
            estimates Delta tau in seconds between adjacent contacts (contact i to i+1).
            Positive indicates contact i leads contact i+1. Non-identifiable pairs
            are reported as NaN.
        adjacent_linearity_r2: 1D array of shape (n_channels - 1,) containing the
            coefficient of determination R^2 of the unwrapped phase-frequency linear fit.
        adjacent_identifiable: 1D boolean array of shape (n_channels - 1,) indicating
            which adjacent pairs satisfy all identifiability criteria (linearity, frequency support,
            unwrapping unambiguous interval).
        mean_wpli: Average wPLI across adjacent contacts; NaN when not computed.
        apparent_velocity_m_s: Apparent phase-delay velocity along the shaft in m/s
            under the fitted linear model (v = pitch_m / tau_per_channel), or None if
            unidentifiable or pitch_um was not provided.
        tau_per_channel_s: Spatial delay gradient in seconds per contact (positive means
            superficial leads deep in input order), or NaN if unidentifiable.
        directionality: String classifying propagation direction:
            - "superficial_to_deep" (tau_per_channel_s > 0)
            - "deep_to_superficial" (tau_per_channel_s < 0)
            - "unidentifiable" (delay identifiability criteria not satisfied)
        delay_identifiable: Boolean indicating whether the phase-frequency relationship
            satisfies the identifiability gate across contacts.
        p_value: Surrogate p-value against the per-channel phase-randomised null, or NaN
            when the test was not performed (``n_surrogates=0``).
        accepted: True only if the surrogate test was performed and significant
            (p <= alpha), coupling is sufficient (mean_wpli >= min_wpli), and the delay
            is identifiable.
        rejection_reason: Diagnostic string explaining rejection, or None if accepted.
        n_channels: Number of channels evaluated.
        pitch_um: Inter-contact spacing in micrometers, if supplied.
    """

    adjacent_wpli: np.ndarray
    adjacent_delays_s: np.ndarray
    adjacent_linearity_r2: np.ndarray
    adjacent_identifiable: np.ndarray
    mean_wpli: float
    apparent_velocity_m_s: Optional[float]
    tau_per_channel_s: float
    directionality: str
    delay_identifiable: bool
    p_value: float
    accepted: bool
    rejection_reason: Optional[str]
    n_channels: int
    pitch_um: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "adjacent_wpli": self.adjacent_wpli.copy(),
            "adjacent_delays_s": self.adjacent_delays_s.copy(),
            "adjacent_linearity_r2": self.adjacent_linearity_r2.copy(),
            "adjacent_identifiable": self.adjacent_identifiable.copy(),
            "mean_wpli": float(self.mean_wpli),
            "apparent_velocity_m_s": float(self.apparent_velocity_m_s) if self.apparent_velocity_m_s is not None else None,
            "tau_per_channel_s": float(self.tau_per_channel_s) if np.isfinite(self.tau_per_channel_s) else np.nan,
            "directionality": str(self.directionality),
            "delay_identifiable": bool(self.delay_identifiable),
            "p_value": float(self.p_value) if np.isfinite(self.p_value) else np.nan,
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "n_channels": int(self.n_channels),
            "pitch_um": float(self.pitch_um) if self.pitch_um is not None else None,
        }


def zflip(
    lfp_matrix: np.ndarray,
    fs: float,
    *,
    freq_range: Tuple[float, float] = (15.0, 35.0),
    pitch_um: Optional[float] = None,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    min_linearity_r2: float = 0.70,
    min_wpli: float = 0.15,
    n_surrogates: int = 50,
    alpha: float = 0.05,
    rng: RNGLike = Default(0),
    seed: Any = Default(0),
) -> ZFlipResult:
    r"""Estimate cortical depth phase gradients, propagation delay, and apparent velocity.

    Evaluates phase slopes across ordered laminar contacts. For a true physical delay
    :math:`\Delta \tau` between contacts :math:`c` and :math:`c+1`, the phase difference
    is linear across frequency:

    .. math::
        \Delta \phi(f) = -2\pi \Delta \tau \cdot f

    where :math:`\Delta \tau = -\frac{1}{2\pi} \frac{d\Delta \phi}{df}`.

    Important Epistemic Invariants & Identifiability Gates:
    1. **Coupling vs. Direction**: wPLI evaluates coupling consistency with reduced
       sensitivity to zero-phase-lag mixing, but is strictly unsigned (:math:`\ge 0`).
       Directionality and delay are derived from the signed phase slope, not wPLI magnitude.
    2. **Identifiability Criteria**: Delay and apparent velocity are defined only when
       every adjacent contact pair satisfies:
       - Linear goodness of fit :math:`R^2 \ge \text{min\_linearity\_r2}` (default 0.70).
       - Frequency support :math:`|F| \ge 3` bins within `freq_range`.
       - Estimated delay within the unambiguous interval :math:`|\Delta \tau| < 1 / (2 \Delta f)`.
         This bounds the estimate, not the true delay: a true delay beyond the interval
         aliases to a smaller estimate that passes, so this check alone cannot detect
         wrapping.
       and the cumulative delay along the shaft is linear in contact index
       (:math:`R^2 \ge 0.5`). If any pair or the spatial fit fails, delay and velocity
       are returned as `NaN` / `None`, and `delay_identifiable = False`. The thresholds
       (0.70, 0.5) are model choices, not derived constants.
    3. **Apparent Velocity**: Reported strictly as *apparent phase-delay velocity under the
       fitted linear model* (:math:`v = \Delta z / \Delta \tau`), not unconditional physical velocity.
    4. **What the delay measures**: :math:`\Delta \tau` is the slope of the phase of the
       segment-averaged cross-spectrum, which is a group delay; it equals the phase delay
       only when the delay does not vary with frequency. Unlike wPLI, that phase is NOT
       insensitive to zero-lag mixing: a zero-lag component shared by adjacent contacts
       pulls the estimate toward 0 (equal-power mixing halves it), and superposed waves
       travelling in opposite directions pull it toward the stronger one. Either can
       still pass every gate, so an accepted delay is an apparent delay under the
       single-wave model.

    Args:
        lfp_matrix: 2D array of shape `(n_channels, n_samples)` ordered along the probe shaft.
            Minimum 3 channels required. Pre-averaged :math:`C \times C \times F` tensors
            are rejected with ValueError because segment information is required for wPLI.
        fs: Sampling frequency in Hz (must be strictly positive).
        freq_range: `(min_freq, max_freq)` in Hz over which the linear phase slope is fitted.
        pitch_um: Inter-contact spacing along the shaft in micrometers (optional).
        nperseg: Welch segment length for STFT; defaults to ``min(max(N // 2, 8), 256)``,
            which keeps at least 2 segments so adjacent wPLI is identifiable.
        noverlap: Segment overlap; defaults to `nperseg // 2`.
        min_linearity_r2: Minimum :math:`R^2` threshold for unwrapped phase linearity (default 0.70).
        min_wpli: Minimum average adjacent wPLI required for acceptance (default 0.15).
        n_surrogates: Number of per-channel Fourier phase-randomised surrogates (default 50).
            ``0`` skips the test: ``p_value`` is NaN and ``accepted`` is False. The smallest
            attainable p-value is ``1 / (n_surrogates + 1)``.
        alpha: Significance threshold in (0, 1) for rejecting the independent-phase null
            (default 0.05).
        rng: Random seed, Generator, or None for fresh entropy, for surrogate
            evaluation (``seed`` is the old spelling and still works).

    Returns:
        :class:`ZFlipResult` container with full diagnostic fields and acceptance flag.

    Raises:
        ValueError: If input is not a finite 2D array of at least 3 channels, `fs <= 0`,
            `freq_range` is not an increasing non-negative pair, `alpha` is outside (0, 1),
            `n_surrogates < 0`, a threshold is outside [0, 1], or the segmentation yields
            fewer than 2 segments.
    """
    seed = resolve_seed_alias(rng, seed, alias_name='seed', func_name='zflip')
    lfp = np.asarray(lfp_matrix, dtype=float)
    if lfp.ndim != 2:
        raise ValueError(
            f"zflip requires a 2D array of shape (n_channels, n_samples); got shape {lfp.shape}."
        )
    n_channels, n_samples = lfp.shape
    if n_channels < 3:
        raise ValueError(f"zflip requires at least 3 channels along the probe shaft; got {n_channels}.")
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive and finite; got {fs}.")
    if pitch_um is not None and (pitch_um <= 0 or not np.isfinite(pitch_um)):
        raise ValueError(f"pitch_um must be strictly positive if provided; got {pitch_um}.")
    if not np.all(np.isfinite(lfp)):
        raise ValueError(
            "zflip requires finite input; NaN or Inf in any contact propagates into every "
            "segment that contains it. Remove or repair those samples first."
        )
    lo, hi = float(freq_range[0]), float(freq_range[1])
    if not (np.isfinite(lo) and np.isfinite(hi) and 0.0 <= lo < hi):
        raise ValueError(f"freq_range must be an increasing non-negative pair; got {freq_range}.")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must lie in (0, 1); got {alpha}.")
    if int(n_surrogates) != n_surrogates or n_surrogates < 0:
        raise ValueError(f"n_surrogates must be a non-negative integer; got {n_surrogates}.")
    n_surrogates = int(n_surrogates)
    for name, value in (("min_linearity_r2", min_linearity_r2), ("min_wpli", min_wpli)):
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"{name} must lie in [0, 1]; got {value}.")

    if nperseg is None:
        # n // 2 rather than the coherence family's n // 8: the phase slope needs >= 3 bins
        # inside a narrow band, so segment length is kept. Unchanged for n >= 512.
        nperseg = min(max(n_samples // 2, MIN_COHERENCE_NPERSEG), 256)
    if noverlap is None:
        noverlap = nperseg // 2
    # One segment saturates wPLI at 1.0 for any input, which would make min_wpli inert.
    _require_identifiable_segmentation(n_samples, nperseg, noverlap, "zflip", "adjacent wPLI")

    # Multi-channel STFT: (n_channels, n_freqs, n_segments)
    freqs, _, Z = signal.stft(
        lfp, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False, axis=-1
    )

    mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
    n_freq_bins = int(np.sum(mask))
    if n_freq_bins < 3:
        return ZFlipResult(
            adjacent_wpli=np.full(n_channels - 1, np.nan),
            adjacent_delays_s=np.full(n_channels - 1, np.nan),
            adjacent_linearity_r2=np.full(n_channels - 1, np.nan),
            adjacent_identifiable=np.zeros(n_channels - 1, dtype=bool),
            mean_wpli=float("nan"),
            apparent_velocity_m_s=None,
            tau_per_channel_s=float("nan"),
            directionality="unidentifiable",
            delay_identifiable=False,
            p_value=float("nan"),
            accepted=False,
            rejection_reason=f"Insufficient frequency bins in freq_range {freq_range} (got {n_freq_bins} bins, need >= 3)",
            n_channels=n_channels,
            pitch_um=pitch_um,
        )

    f_band = freqs[mask]
    df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    max_tau_unambiguous = 1.0 / (2.0 * df) if df > 0 else np.inf

    adj_wpli = np.zeros(n_channels - 1, dtype=float)
    adj_delays = np.zeros(n_channels - 1, dtype=float)
    adj_r2 = np.zeros(n_channels - 1, dtype=float)
    adj_identifiable = np.zeros(n_channels - 1, dtype=bool)

    for i in range(n_channels - 1):
        # S_{i, i+1, k} = conj(Z[i]) * Z[i+1]
        Sxy = np.conj(Z[i]) * Z[i + 1]  # (n_freqs, n_segments)
        w_f, _ = _wpli_from_cross_spectra(Sxy)
        adj_wpli[i] = float(np.mean(w_f[mask]))

        # Phase slope from average cross-spectrum across segments
        Sxy_mean = np.mean(Sxy, axis=1)
        phi = np.unwrap(np.angle(Sxy_mean[mask]))
        res = stats.linregress(f_band, phi)
        r2 = float(res.rvalue ** 2) if np.isfinite(res.rvalue) else 0.0
        adj_r2[i] = r2

        slope = float(res.slope)
        tau = -slope / (2.0 * np.pi)
        adj_delays[i] = tau

        if r2 >= min_linearity_r2 and abs(tau) < max_tau_unambiguous:
            adj_identifiable[i] = True

    mean_wpli_val = float(np.mean(adj_wpli))

    # Every adjacent pair must be identifiable. The cumulative delay sums all pairs, so a
    # non-identifiable pair's delay would enter the spatial fit: one incoherent contact
    # biased 12-contact estimates by ~16%, and on 3 contacts a single identifiable pair
    # was accepted with the wrong sign.
    delay_identifiable = bool(np.all(adj_identifiable))

    if delay_identifiable:
        # Cumulative phase delay along the array
        cum_delay = np.zeros(n_channels, dtype=float)
        cum_delay[1:] = np.cumsum(adj_delays)
        coords = np.arange(n_channels, dtype=float)
        reg_spatial = stats.linregress(coords, cum_delay)
        tau_per_channel = float(reg_spatial.slope)
        spatial_r2 = float(reg_spatial.rvalue ** 2) if np.isfinite(reg_spatial.rvalue) else 0.0

        if spatial_r2 < 0.50:
            delay_identifiable = False
            tau_per_channel = float("nan")
            apparent_velocity = None
            directionality = "unidentifiable"
        else:
            if tau_per_channel > 0:
                directionality = "superficial_to_deep"
            elif tau_per_channel < 0:
                directionality = "deep_to_superficial"
            else:
                delay_identifiable = False
                tau_per_channel = float("nan")
                directionality = "unidentifiable"

            if pitch_um is not None and np.isfinite(tau_per_channel):
                pitch_m = float(pitch_um) * 1e-6
                apparent_velocity = float(abs(pitch_m / tau_per_channel))
            else:
                apparent_velocity = None
    else:
        tau_per_channel = float("nan")
        apparent_velocity = None
        directionality = "unidentifiable"

    # Monte Carlo surrogate null test
    rng = np.random.default_rng(seed)
    p_val = float("nan")
    if n_surrogates > 0:
        exceed_count = 0
        for _ in range(n_surrogates):
            surr_lfp = _surrogate_phase_randomize(lfp, rng)
            _, _, Z_surr = signal.stft(
                surr_lfp, fs=fs, nperseg=nperseg, noverlap=noverlap, boundary=None, padded=False, axis=-1
            )
            surr_adj_wpli = np.zeros(n_channels - 1, dtype=float)
            for i in range(n_channels - 1):
                w_s, _ = _wpli_from_cross_spectra(np.conj(Z_surr[i]) * Z_surr[i + 1])
                surr_adj_wpli[i] = float(np.mean(w_s[mask]))
            if np.mean(surr_adj_wpli) >= mean_wpli_val:
                exceed_count += 1
        p_val = float((1 + exceed_count) / (1 + n_surrogates))

    # No test performed means no inferential acceptance.
    is_sig = bool(np.isfinite(p_val) and p_val <= alpha)
    has_coupling = (mean_wpli_val >= min_wpli)
    accepted = bool(is_sig and has_coupling and delay_identifiable)

    reasons: List[str] = []
    if n_surrogates == 0:
        reasons.append("Surrogate test not performed (n_surrogates=0)")
    elif not is_sig:
        reasons.append(f"Non-significant coupling vs phase surrogates (p = {p_val:.4f} > {alpha})")
    if not has_coupling:
        reasons.append(f"Mean adjacent wPLI ({mean_wpli_val:.4f}) below min_wpli ({min_wpli:.4f})")
    if not delay_identifiable:
        reasons.append("Phase-frequency relation failed linear identifiability gate")

    rejection_reason = "; ".join(reasons) if not accepted else None

    # Replace non-identifiable individual adjacent delays with NaN
    cleaned_delays = adj_delays.copy()
    cleaned_delays[~adj_identifiable] = np.nan

    return ZFlipResult(
        adjacent_wpli=adj_wpli,
        adjacent_delays_s=cleaned_delays,
        adjacent_linearity_r2=adj_r2,
        adjacent_identifiable=adj_identifiable,
        mean_wpli=mean_wpli_val,
        apparent_velocity_m_s=apparent_velocity,
        tau_per_channel_s=tau_per_channel,
        directionality=directionality,
        delay_identifiable=delay_identifiable,
        p_value=p_val,
        accepted=accepted,
        rejection_reason=rejection_reason,
        n_channels=n_channels,
        pitch_um=pitch_um,
    )




