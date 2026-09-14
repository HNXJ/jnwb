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
from scipy import signal

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
    low_peak_contact: Optional[int]
    high_peak_contact: Optional[int]
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
            "low_peak_contact": int(self.low_peak_contact) if self.low_peak_contact is not None else None,
            "high_peak_contact": int(self.high_peak_contact) if self.high_peak_contact is not None else None,
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
        )

    # 3. Frequency standardization across valid contacts along the shaft
    clean_psd = psd_work.copy()
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
            if probe_geometry is not None and order is not None:
                sorted_z = probe_geometry.contact_positions[order, 2]
                if np.ptp(sorted_z) > 1e-6:
                    crossover_z = float(np.interp(crossover_c, np.arange(n_channels), sorted_z))
                elif effective_spacing is not None:
                    crossover_z = float(crossover_c * effective_spacing)
            elif effective_spacing is not None:
                crossover_z = float(crossover_c * effective_spacing)

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


def vflip_from_lfp(
    lfp: np.ndarray,
    fs: float,
    *,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    window: str = "hann",
    detrend: Union[str, bool] = "constant",
    scaling: str = "density",
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
) -> Dict[Any, str]:
    """Assign cortical layer labels (superficial, input, deep) to probe contacts.

    Maps contacts along a linear probe shaft into canonical cortical compartments:
    - ``"superficial"``: Supragranular layers (L1–L3), characterized by gamma dominance.
    - ``"input"``: Granular layer 4 (L4), centered at the spectrolaminar crossover point,
      extending across a zone of width `granular_thickness_um`.
    - ``"deep"``: Infragranular layers (L5–L6), characterized by alpha/beta dominance.
    - ``"na"``: Assigned to all channels whenever `vflip_result.accepted` is `False`, or to
      invalid/out-of-bounds contacts.

    Critical Invariant:
    Rejected or non-identifiable fits (`vflip_result.accepted is False`) strictly map
    **all** channels to ``"na"``. Never guesses or imputes layers on failed fits.

    Args:
        vflip_result: :class:`VFlipResult` container from :func:`vflip` or :func:`vflip_from_lfp`.
        probe_geometry: :class:`jnwb.ProbeGeometry` describing the physical contact positions
            and ordering along the linear probe shaft. Must satisfy `is_linear=True`.
        granular_thickness_um: Thickness of the granular layer (input zone) in micrometers (um).
            Must be strictly positive and finite (default: 400.0 um).

    Returns:
        Dictionary mapping channel identifier (from `probe_geometry.channel_ids`) to layer label
        string: ``"superficial"``, ``"input"``, ``"deep"``, or ``"na"``.

    Raises:
        ValueError: If `granular_thickness_um` is non-positive or non-finite, `probe_geometry`
            is not linear, or channel count does not match `vflip_result.n_channels`.

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
    for idx, ch_id in enumerate(channel_ids):
        c_pos = float(rank[idx])
        if input_start <= c_pos <= input_end:
            labels[ch_id] = "input"
        elif c_pos < input_start:
            labels[ch_id] = "superficial" if is_sup_to_deep else "deep"
        else:  # c_pos > input_end
            labels[ch_id] = "deep" if is_sup_to_deep else "superficial"

    return labels


