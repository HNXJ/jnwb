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
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

from ._backend import resolve_device

log = logging.getLogger(__name__)

CANONICAL_VFLIP_BANDS: Dict[str, Tuple[float, float]] = {
    "low": (8.0, 30.0),    # infragranular (deep) alpha/beta dominance
    "high": (50.0, 150.0),  # supragranular (superficial) gamma dominance
}


@dataclass(frozen=True)
class VFlipResult:
    """Container for Vectorized Frequency-based Laminar Identity Profile (vFLIP) results.

    Attributes:
        crossover_contact: Continuous sub-contact coordinate where the spectrolaminar profile
            crosses zero between low-frequency and high-frequency dominance peaks, or None if rejected.
        crossover_depth_um: Physical cortical depth of the crossover in micrometers (um) along
            the ordered contacts, or None if rejected or contact spacing is unavailable.
        support_score: Support metric Omega evaluating contrast magnitude, peak separation,
            and transition sharpness. Returned for both accepted and rejected fits.
        profile: 1D array of shape (n_channels,) containing the standardized spectrolaminar
            difference profile Delta(c) along the ordered contacts.
        low_peak_contact: Integer contact index of the low-frequency (alpha/beta) power peak.
        high_peak_contact: Integer contact index of the high-frequency (gamma) power peak.
        orientation: Resolved orientation string ('superficial_to_deep' or 'deep_to_superficial').
        accepted: Boolean flag indicating whether the spectrolaminar motif satisfies all
            acceptance criteria (support score >= threshold, valid monotonic crossover).
        rejection_reason: Diagnostic reason string if rejected, or None if accepted.
        n_channels: Total number of evaluated contacts along the probe shaft.
        n_missing: Number of bad or missing contacts interpolated or masked during fitting.
    """

    crossover_contact: Optional[float]
    crossover_depth_um: Optional[float]
    support_score: float
    profile: np.ndarray
    low_peak_contact: int
    high_peak_contact: int
    orientation: str
    accepted: bool
    rejection_reason: Optional[str]
    n_channels: int
    n_missing: int

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "crossover_contact": self.crossover_contact,
            "crossover_depth_um": self.crossover_depth_um,
            "support_score": float(self.support_score),
            "profile": self.profile.copy(),
            "low_peak_contact": int(self.low_peak_contact),
            "high_peak_contact": int(self.high_peak_contact),
            "orientation": str(self.orientation),
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "n_channels": int(self.n_channels),
            "n_missing": int(self.n_missing),
        }


def vflip(
    psd: np.ndarray,
    freqs: np.ndarray,
    *,
    band_low: Tuple[float, float] = (8.0, 30.0),
    band_high: Tuple[float, float] = (50.0, 150.0),
    contact_spacing: Optional[float] = None,
    probe_geometry: Optional[Any] = None,
    orientation: str = "auto",
    min_support_score: float = 6.0,
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
        1. Standardizes power per frequency across contacts along the shaft:
           :math:`\\tilde{P}(c, f) = (P(c, f) - \\mu_c(f)) / \\sigma_c(f)`.
        2. Computes low-band and high-band power profiles across contacts:
           :math:`L(c) = \\frac{1}{|F_{\\text{low}}|} \\sum_{f \\in F_{\\text{low}}} \\tilde{P}(c, f)`,
           :math:`H(c) = \\frac{1}{|F_{\\text{high}}|} \\sum_{f \\in F_{\\text{high}}} \\tilde{P}(c, f)`.
        3. Forms the signed spectrolaminar difference profile:
           :math:`\\Delta(c) = H(c) - L(c)` (oriented superficial to deep).
        4. Identifies continuous sub-contact zero-crossing root :math:`c^*`:
           :math:`c^* = i + \\frac{-\\Delta(i)}{\\Delta(i+1) - \\Delta(i)}`
           located between the high-frequency peak :math:`c_{\\text{high}}` and low-frequency peak :math:`c_{\\text{low}}`.
        5. Evaluates the support score :math:`\\Omega` based on contrast magnitude, spatial peak separation,
           and transition monotonicity. If :math:`\\Omega < \\Omega_{\\text{thresh}}` or no valid crossover exists,
           the fit is rejected (`accepted=False`, `crossover_contact=None`).

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
        min_support_score: Minimum support score Omega required to accept the fit (default: 6.0).
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

    # Validate device
    _ = resolve_device(device, context="vflip", prefer="cupy", stacklevel=3)

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

    n_missing = int(np.sum(bad_mask))
    n_valid = n_channels - n_missing

    if n_valid < min_channels:
        # Rejection: insufficient valid channels
        dummy_profile = np.zeros(n_channels)
        return VFlipResult(
            crossover_contact=None,
            crossover_depth_um=None,
            support_score=-np.inf,
            profile=dummy_profile,
            low_peak_contact=0,
            high_peak_contact=0,
            orientation="undetermined",
            accepted=False,
            rejection_reason="insufficient_channels",
            n_channels=n_channels,
            n_missing=n_missing,
        )

    # 3. Frequency standardization across valid contacts
    clean_psd = psd_arr.copy()
    # Interpolate missing channels along depth before standardization
    valid_idx = np.where(~bad_mask)[0]
    if n_missing > 0:
        for f_idx in range(n_freqs):
            clean_psd[:, f_idx] = np.interp(np.arange(n_channels), valid_idx, clean_psd[valid_idx, f_idx])

    # Z-score normalize per frequency across contacts
    col_means = np.mean(clean_psd, axis=0)
    col_stds = np.std(clean_psd, axis=0)
    col_stds[col_stds < 1e-12] = 1e-12
    normed_psd = (clean_psd - col_means) / col_stds

    # 4. Band profiles
    low_profile = np.mean(normed_psd[:, mask_low], axis=1)
    high_profile = np.mean(normed_psd[:, mask_high], axis=1)

    low_peak = int(np.argmax(low_profile))
    high_peak = int(np.argmax(high_profile))

    # 5. Orientation resolution
    if orientation == "auto":
        if high_peak < low_peak:
            resolved_orientation = "superficial_to_deep"
            signed_profile = high_profile - low_profile
        elif low_peak < high_peak:
            resolved_orientation = "deep_to_superficial"
            signed_profile = low_profile - high_profile
        else:
            resolved_orientation = "undetermined"
            signed_profile = high_profile - low_profile
    elif orientation == "superficial_to_deep":
        resolved_orientation = "superficial_to_deep"
        signed_profile = high_profile - low_profile
    else:  # deep_to_superficial
        resolved_orientation = "deep_to_superficial"
        signed_profile = low_profile - high_profile

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
            v1 = signed_profile[i]
            v2 = signed_profile[i + 1]
            if (v1 >= 0 and v2 <= 0) or (v1 <= 0 and v2 >= 0):
                denom = v1 - v2
                if abs(denom) > 1e-12:
                    sub_c = float(i + (v1 / denom))
                else:
                    sub_c = float(i + 0.5)
                # Keep within interval
                sub_c = min(float(i + 1), max(float(i), sub_c))
                steepness = abs(v1 - v2)
                cross_candidates.append((sub_c, steepness))

        if cross_candidates:
            # Select candidate maximizing transition steepness
            cross_candidates.sort(key=lambda x: x[1], reverse=True)
            crossover_c = cross_candidates[0][0]
            if effective_spacing is not None:
                crossover_z = crossover_c * effective_spacing

    # 8. Support Score (Omega) Formulation
    # Components:
    # 1. Spectral pole distance between low-peak and high-peak contact across standardized frequencies
    p_dist = float(np.linalg.norm(normed_psd[high_peak] - normed_psd[low_peak]))
    # 2. Band difference profile Euclidean distance across contacts
    band_dist = float(np.linalg.norm(signed_profile))
    # 3. Contrast magnitude across poles:
    # High-frequency dominance at high peak + Low-frequency dominance at low peak
    contrast = float(
        (high_profile[high_peak] - low_profile[high_peak])
        + (low_profile[low_peak] - high_profile[low_peak])
    )
    # 4. Spatial separation in channels
    sep_metric = float(max(1, peak_sep))

    metric = p_dist * band_dist * max(1e-4, contrast) * sep_metric
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
        profile=signed_profile,
        low_peak_contact=low_peak,
        high_peak_contact=high_peak,
        orientation=resolved_orientation,
        accepted=accepted,
        rejection_reason=rejection_reason,
        n_channels=n_channels,
        n_missing=n_missing,
    )
