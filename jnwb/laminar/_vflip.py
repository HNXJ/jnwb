"""vFLIP: the spectrolaminar crossover from relative power across contacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
from .._dictlike import DictAccessMixin
from scipy import signal
from .._backend import CUDA, resolve_device, warn_no_gpu_path


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
        crossover_depth_um: Depth of the crossover along the ordered contacts in micrometers
            (um): ``crossover_contact`` times the contact spacing, measured from the first
            contact of the order the fit used -- `probe_geometry.linear_order`, whose
            direction follows the electrode table's row order, or the row order itself
            without a geometry. With a `probe_geometry` the spacing is its `nominal_pitch`
            (a disagreeing `contact_spacing` raises), so this is the frame
            :func:`label_layers` places contacts in (its `depth_range_um` compares against
            rank times `nominal_pitch`), whatever the geometry's z coordinates are. None if
            rejected or no contact spacing is available.
        crossover_z_um: The crossover's z coordinate in the geometry's own frame, in
            micrometers, interpolated between the z of the two contacts either side of it
            along the shaft. It keeps the table's origin and direction, so on a shaft whose
            z falls with depth it falls as ``crossover_depth_um`` rises. None if rejected,
            if no `probe_geometry` was given, or if z does not vary along the shaft.
        support_score: Support metric Omega evaluating contrast magnitude, peak separation,
            and transition sharpness, as the natural logarithm of their density-normalized
            product. Returned for both accepted and rejected fits; ``-inf`` when that
            product is zero or too few channels are valid, so no finite
            `min_support_score` accepts such a fit.
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
            ``"declaration_contradicted"`` means a depth declaration put the shallow contact
            first and a motif that passed every other acceptance test resolved as
            ``"deep_to_superficial"`` in that frame.
        n_channels: Total number of evaluated contacts along the probe shaft.
        n_missing: Number of bad or missing contacts interpolated or masked during fitting.
        bad_channel_mask: Optional boolean array of shape (n_channels,) indicating bad or
            masked contacts in input channel order.
        index_space: Which axis ``crossover_contact``, ``profile``, ``low_peak_contact`` and
            ``high_peak_contact`` are indexed on.

            - ``"shaft_rank"``: position along the physical shaft, starting from the end
              `depth_anchor` names: the declared shallow contact under ``"shallowest"``,
              the first contact of `linear_order` (which follows the table's row order and
              may be the deep one) under ``"row_order"``. Produced when `vflip` was given a
              `probe_geometry` carrying a usable `linear_order`, which reorders the PSD rows
              before the fit.
            - ``"channel"``: the row order of the PSD array as supplied. Produced when no
              geometry was given, so no reordering happened.

            The two coincide only when the electrode table is already ordered along the
            shaft. :func:`label_layers` always reads shaft-rank, so it refuses a
            ``"channel"`` result whenever the geometry it is handed has a non-identity
            `linear_order` rather than mixing the two axes silently.
        depth_anchor: Which end of the shaft rank 0 is, and so where ``crossover_depth_um``
            is measured from.

            - ``"row_order"``: the first contact of `probe_geometry.linear_order`, whose
              direction follows the electrode table's row order, or the first PSD row
              without a geometry. Produced when no depth axis was declared.
            - ``"shallowest"``: the contact at the declared shallow end of `depth_axis`, so
              depth increases into tissue whatever the row order. Produced when `vflip`
              was given `depth_axis` and `shallow_end`.

            :func:`label_layers` must be given the same declaration.
        depth_axis: The declared depth column of `probe_geometry.contact_positions`
            (``"x"``, ``"y"`` or ``"z"``), or None.
        shallow_end: Which end of `depth_axis` is shallow, ``"min"`` or ``"max"``, or None.
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
    index_space: str = "channel"
    crossover_z_um: Optional[float] = None
    depth_anchor: str = "row_order"
    depth_axis: Optional[str] = None
    shallow_end: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result container to dictionary for serialization."""
        return {
            "crossover_contact": self.crossover_contact,
            "crossover_depth_um": self.crossover_depth_um,
            "crossover_z_um": self.crossover_z_um,
            "depth_anchor": str(self.depth_anchor),
            "depth_axis": self.depth_axis,
            "shallow_end": self.shallow_end,
            "support_score": float(self.support_score),
            "profile": self.profile.copy(),
            "low_peak_contact": int(self.low_peak_contact) if self.low_peak_contact is not None else None,
            "high_peak_contact": int(self.high_peak_contact) if self.high_peak_contact is not None else None,
            "orientation": str(self.orientation),
            "accepted": bool(self.accepted),
            "rejection_reason": self.rejection_reason,
            "n_channels": int(self.n_channels),
            "n_missing": int(self.n_missing),
            "index_space": str(self.index_space),
        }


# Geometry columns a caller may declare as the depth axis, as `contact_positions` columns,
# and which end of that axis is shallow.
_DEPTH_AXES = ("x", "y", "z")
_SHALLOW_ENDS = ("min", "max")
#: Fewest frequency bins :func:`vflip` accepts, as its own check on ``freqs`` states.
_MIN_FREQ_BINS = 4


def _refuse_a_deep_first_declaration(
    orientation: str, depth_axis: Optional[str], shallow_end: Optional[str], func_name: str
) -> None:
    """A depth declaration puts the shallow contact first, so contact 0 cannot also be deep."""
    if orientation == "deep_to_superficial" and (depth_axis is not None or shallow_end is not None):
        raise ValueError(
            f"{func_name}: orientation='deep_to_superficial' says contact 0 is deep, but "
            f"depth_axis={depth_axis!r} with shallow_end={shallow_end!r} puts the shallow "
            "contact first. Pass orientation='auto' or 'superficial_to_deep' with the "
            "declaration, or drop the declaration."
        )


def _depth_anchored_order(
    probe_geometry: Any,
    order: Optional[np.ndarray],
    depth_axis: Optional[str],
    shallow_end: Optional[str],
    func_name: str,
) -> Tuple[Optional[np.ndarray], str]:
    """The shaft order to fit and label in, and the anchor it carries.

    Without a declaration the order is `probe_geometry.linear_order` as given, whose direction
    follows the table's row order ('row_order'). With one, the order is reversed when needed so
    rank 0 is the contact at the declared shallow end ('shallowest'). The geometry itself is
    never modified.
    """
    if depth_axis is None and shallow_end is None:
        return order, "row_order"
    if depth_axis is None or shallow_end is None:
        raise ValueError(
            f"{func_name}: depth_axis and shallow_end are declared together; got "
            f"depth_axis={depth_axis!r}, shallow_end={shallow_end!r}"
        )
    if depth_axis not in _DEPTH_AXES:
        raise ValueError(f"{func_name}: depth_axis must be one of {_DEPTH_AXES}, got {depth_axis!r}")
    if shallow_end not in _SHALLOW_ENDS:
        raise ValueError(
            f"{func_name}: shallow_end must be one of {_SHALLOW_ENDS}, got {shallow_end!r}"
        )
    positions = getattr(probe_geometry, "contact_positions", None)
    if probe_geometry is None or positions is None:
        raise ValueError(
            f"{func_name}: a depth_axis declaration needs a probe_geometry with contact_positions"
        )
    positions = np.asarray(positions, dtype=float)
    column = _DEPTH_AXES.index(depth_axis)
    if positions.ndim != 2 or positions.shape[1] <= column:
        raise ValueError(
            f"{func_name}: probe_geometry.contact_positions has no {depth_axis!r} column "
            f"(shape {positions.shape})"
        )
    if order is None or len(order) != positions.shape[0]:
        raise ValueError(
            f"{func_name}: a depth_axis declaration needs probe_geometry.linear_order over "
            "every contact"
        )
    first, last = positions[order[0], column], positions[order[-1], column]
    if not (np.isfinite(first) and np.isfinite(last)) or abs(last - first) <= 1e-6:
        raise ValueError(
            f"{func_name}: {depth_axis!r} does not change between the two ends of the shaft "
            f"({first} and {last} um), so it cannot say which end is shallow"
        )
    # Depth is monotone along the shaft; a column that rises and falls along it, as the
    # lateral column of a staggered shaft does, is not depth.
    steps = np.diff(positions[np.asarray(order), column])
    if not np.all(np.isfinite(steps)) or (np.any(steps > 1e-6) and np.any(steps < -1e-6)):
        raise ValueError(
            f"{func_name}: {depth_axis!r} is not monotone along the shaft, as the lateral "
            "column of a staggered shaft is not, so it is not a depth axis"
        )
    shallow_first = first < last if shallow_end == "min" else first > last
    return (np.asarray(order) if shallow_first else np.asarray(order)[::-1]), "shallowest"


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
    depth_axis: Optional[str] = None,
    shallow_end: Optional[str] = None,
) -> VFlipResult:
    """Vectorized Frequency-based Laminar Identity Profile (vFLIP).

    Estimates the spectrolaminar transition (layer 4 / granular crossover) along a linear
    multichannel probe from precomputed power spectral density (PSD) profiles.

    Evaluates the canonical spectrolaminar motif (Mendoza-Halliday et al. 2024), where
    supragranular (superficial) layers exhibit predominant high-frequency (gamma) power
    and infragranular (deep) layers exhibit predominant low-frequency (alpha/beta) power.

    `vflip` shares its name with the FLIP and the frequency-variable vFLIP of that paper,
    not their procedure. The paper divides each frequency by the power of the channel with
    the highest power, uses 10-19 Hz and 75-150 Hz, and fits linear regressions over the
    channel range that maximizes a goodness of fit; vFLIP also searches over band pairs.
    `vflip` normalizes by the range across contacts, uses fixed default bands and scores the
    fit by its support score Omega, so its crossover is not a FLIP or vFLIP crossover.

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
        contact_spacing: Inter-contact spacing (pitch) in micrometers (um). With a
            `probe_geometry` it defaults to `probe_geometry.nominal_pitch` and must equal it.
        probe_geometry: Optional :class:`jnwb.ProbeGeometry` object validating probe linearity and
            contact ordering along the shaft.
        orientation: Expected shaft orientation relative to the fitted contact order, whose
            contact 0 is the declared shallow contact under a depth declaration, the first
            contact of `probe_geometry.linear_order` otherwise, and PSD row 0 without a
            geometry:
            - ``"auto"``: Automatically evaluates peak ordering and resolves orientation.
            - ``"superficial_to_deep"``: Requires contact 0 to be superficial (gamma peaks before alpha/beta).
            - ``"deep_to_superficial"``: Requires contact 0 to be deep (alpha/beta peaks before gamma).
              Raises ValueError with a depth declaration, which puts the shallow contact
              first; with ``"auto"``, a declared fit that resolves this way is rejected
              (see `shallow_end`).
        min_support_score: Minimum support score Omega required to accept the fit (default: 3.75).
            Must be a finite float; no sentinels (e.g. -inf) may bypass acceptance logic.
        bad_channel_mask: Optional boolean mask of shape `(n_channels,)` flagging invalid/detached contacts.
        min_channels: Minimum number of valid channels required along the shaft (default: 8).
        min_peak_distance: Minimum channel distance required between low and high power peaks (default: 2).
        device: Hardware device (`"cpu"` or `"cuda"`).
        depth_axis: Optional column of `probe_geometry.contact_positions` that is depth:
            ``"x"``, ``"y"`` or ``"z"``. Declared together with `shallow_end`. With the
            declaration the fit runs along the shaft from its shallow end, so
            ``crossover_contact``, the peaks, the profile, `orientation` and
            ``crossover_depth_um`` are anchored there and do not depend on the table's row
            order; the result records ``depth_anchor="shallowest"``. Without it they follow
            `linear_order` as given (``depth_anchor="row_order"``), unchanged. The geometry
            is never modified. ``"x"``, ``"y"`` and ``"z"`` name columns 0, 1 and 2 of
            `contact_positions`, so ``"z"`` is the table's ``rel_z`` when it has no
            ``x``/``y``/``z`` columns. The axis is refused when its values at the two end
            contacts of the shaft are within 1e-6 um of each other, or when it is not
            monotone along the shaft (steps of 1e-6 um or less count as level), as the
            lateral column of a staggered shaft is not.
        shallow_end: Which end of `depth_axis` is shallow: ``"min"`` or ``"max"``. jnwb
            does not infer it, because coordinate conventions differ between files. A
            motif that places the deep layers at the declared shallow end rejects the fit
            (``rejection_reason="declaration_contradicted"``) rather than overriding either.
            That reason is reported only for a fit that passes every other acceptance test,
            so a fit without support reports ``"insufficient_support"``; an
            ``orientation`` argument that the peaks disagree with reports
            ``"orientation_mismatch"`` first.

    Returns:
        :class:`VFlipResult` containing the estimated crossover contact, depth, support score,
        and diagnostic flags.

    Raises:
        ValueError: If input dimensions are invalid, frequencies non-monotonic, bands overlapping
            or outside frequency range, non-finite parameters provided, min_support_score is
            non-finite, `contact_spacing` disagrees with `probe_geometry.nominal_pitch`
            (the depth would then not be in the frame :func:`label_layers` measures),
            ``orientation="deep_to_superficial"`` comes with a depth declaration, or the
            depth declaration is incomplete, names an unknown axis or end, comes without a
            `probe_geometry`, or names an axis that does not change along the shaft or is
            not monotone along it.
    """
    # 1. Parameter validation
    if not np.isfinite(min_support_score):
        raise ValueError(f"min_support_score must be a finite float, got {min_support_score}")

    valid_orientations = ("auto", "superficial_to_deep", "deep_to_superficial")
    if orientation not in valid_orientations:
        raise ValueError(f"orientation must be one of {valid_orientations}, got {orientation!r}")
    _refuse_a_deep_first_declaration(orientation, depth_axis, shallow_end, "vflip")

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
        nominal = getattr(probe_geometry, "nominal_pitch", None)
        if effective_spacing is None:
            effective_spacing = nominal
        elif nominal is not None and not np.isclose(
            float(effective_spacing), float(nominal), rtol=1e-9, atol=0.0
        ):
            # label_layers measures depth as rank times nominal_pitch, so a depth computed
            # with another spacing would select different contacts through depth_range_um.
            raise ValueError(
                f"contact_spacing={contact_spacing} disagrees with probe_geometry.nominal_pitch="
                f"{nominal}; label_layers measures depth with nominal_pitch, so the crossover "
                "depth would not be in its frame. Omit contact_spacing, or build the geometry "
                "with nominal_pitch=contact_spacing."
            )
        order = getattr(probe_geometry, "linear_order", None)
    order, depth_anchor = _depth_anchored_order(
        probe_geometry, order, depth_axis, shallow_end, "vflip"
    )

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

    # If probe_geometry is provided, order channels along the physical shaft.
    #
    # Everything downstream -- the profile, the two peak contacts and the crossover --
    # is then indexed on shaft rank rather than on PSD row. Without a usable
    # `linear_order` no reorder happens and those indices stay in PSD row order. The two
    # axes coincide only for a table already ordered along the shaft, so which one was
    # used travels on the result and is checked at the `label_layers` boundary.
    if order is not None and len(order) == n_channels:
        psd_work = psd_arr[order]
        bad_mask = bad_mask[order]
        index_space = "shaft_rank"
    else:
        psd_work = psd_arr
        index_space = "channel"

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
            index_space=index_space,
            depth_anchor=depth_anchor,
            depth_axis=depth_axis,
            shallow_end=shallow_end,
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
    crossover_depth: Optional[float] = None
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
            # Depth is always shaft rank times pitch, the frame `label_layers` places
            # contacts in. The geometry's own z is reported separately: it can run in
            # either direction along the shaft and carries the table's origin, so it is a
            # different quantity rather than a more precise depth.
            if effective_spacing is not None:
                crossover_depth = float(crossover_c * effective_spacing)
            if probe_geometry is not None and order is not None and len(order) == n_channels:
                sorted_z = np.asarray(probe_geometry.contact_positions, dtype=float)[order, 2]
                if np.ptp(sorted_z) > 1e-6:
                    crossover_z = float(np.interp(crossover_c, np.arange(n_channels), sorted_z))

    # 8. Support Score (Omega) Formulation
    # Density-normalized so the score does not scale with the number of channels.
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
    # No floor: a floor reported every metric below it as one finite score, which a caller
    # threshold under that score accepted. A metric of zero has no support at all.
    support_score = float(np.log(metric)) if metric > 0 else -np.inf

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
    elif depth_anchor == "shallowest" and resolved_orientation == "deep_to_superficial":
        # Checked last: only a motif that passes every other test can contradict the
        # declaration. On noise the peak order is a coin toss, and reporting it as a
        # contradiction would name the wrong reason for a fit that has no support.
        accepted = False
        rejection_reason = "declaration_contradicted"

    # Enforce failure invariants: rejected fit implies None crossover
    final_cross_c = crossover_c if accepted else None
    final_cross_depth = crossover_depth if accepted else None
    final_cross_z = crossover_z if accepted else None

    return VFlipResult(
        crossover_contact=final_cross_c,
        crossover_depth_um=final_cross_depth,
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
        index_space=index_space,
        crossover_z_um=final_cross_z,
        depth_anchor=depth_anchor,
        depth_axis=depth_axis,
        shallow_end=shallow_end,
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
    depth_axis: Optional[str] = None,
    shallow_end: Optional[str] = None,
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
            yielding a nominal ~1 Hz frequency resolution). From 6, the shortest segment
            that gives the 4 frequency bins :func:`vflip` needs, to `n_times`; a default
            below 6 raises `ValueError` like an explicit one.
        noverlap: Number of points to overlap between segments (default: `nperseg // 2`).
        window: Window specification for periodogram calculation (default: `'hann'`).
        detrend: Specifies how to detrend each segment (default: `'constant'`).
        scaling: Selects between computing power spectral density (`'density'`) and
            power spectrum (`'spectrum'`). Default: `'density'`.
        band_low: Frequency range (f_min, f_max) in Hz for the low-frequency band (default: 8-30 Hz).
        band_high: Frequency range (f_min, f_max) in Hz for the high-frequency band (default: 50-150 Hz).
        contact_spacing: Inter-contact spacing (pitch) in micrometers (um). With a
            `probe_geometry` it defaults to `probe_geometry.nominal_pitch` and must equal it.
        probe_geometry: Optional :class:`jnwb.ProbeGeometry` object validating probe linearity and
            contact ordering along the shaft.
        orientation: Expected shaft orientation relative to the fitted contact order, as in
            :func:`vflip` (contact 0 is the declared shallow contact under a depth
            declaration):
            - ``"auto"``: Automatically evaluates peak ordering and resolves orientation.
            - ``"superficial_to_deep"``: Requires contact 0 to be superficial (gamma peaks before alpha/beta).
            - ``"deep_to_superficial"``: Requires contact 0 to be deep (alpha/beta peaks before gamma).
              Raises ValueError with a depth declaration, before the PSD is computed.
        min_support_score: Minimum support score Omega required to accept the fit (default: 3.75).
            Must be a finite float; no sentinels (e.g. -inf) may bypass acceptance logic.
        bad_channel_mask: Optional boolean mask of shape `(n_channels,)` flagging invalid/detached contacts.
            A channel with any NaN or Inf sample is also treated as bad: it is excluded,
            interpolated along depth like a masked contact, and counted in
            ``VFlipResult.n_missing``.
        min_channels: Minimum number of valid channels required along the shaft (default: 8).
        min_peak_distance: Minimum channel distance required between low and high power peaks (default: 2).
        device: Hardware device (`"cpu"` or `"cuda"`).
        depth_axis, shallow_end: Optional depth declaration, passed to :func:`vflip`, which
            anchors the fit at the shallow end of the declared geometry column.

    Returns:
        :class:`VFlipResult` containing the estimated crossover contact, depth, support score,
        and diagnostic flags.

    Raises:
        ValueError: If `lfp` is not 2D, `fs` is non-positive or non-finite, `contact_spacing`
            disagrees with `probe_geometry.nominal_pitch`, the depth declaration is invalid
            (as in :func:`vflip`), or parameters violate geometry, frequency, or numerical
            invariants.

    References:
        Mendoza-Halliday, D., et al. (2024). A ubiquitous spectrolaminar motif of local field
        potential power across the primate cortex. Nature Neuroscience.
        doi:10.1038/s41593-023-01554-7 -- the spectrolaminar motif :func:`vflip` tests for;
        the :func:`vflip` docstring says how its estimator differs from the paper's FLIP
        and vFLIP.
        Bastos, A. M., et al. (2018). Laminar recordings in frontal cortex suggest distinct
        layers for maintenance and control of working memory. PNAS.
        doi:10.1073/pnas.1710323115 -- Results, "Gamma Power Peaks in Superficial Layers
        and Alpha/Beta Peaks in Deep Layers", and Fig. 2B: power at each frequency relative
        to the other contacts, averaged into a low-band and a high-band depth profile, whose
        crossover lies near the first current source density sink. The paper divides by the
        largest power across contacts and averages 4-22 Hz and 58-260 Hz (50-250 Hz in the
        Fig. 2 legend); step 1 of :func:`vflip` also subtracts the smallest, the default
        bands are 8-30 Hz and 50-150 Hz, and step 3 rescales each profile before the
        crossing is found.
        Bastos, A. M., et al. (2021). Neural effects of propofol-induced unconsciousness and
        its reversal using thalamic stimulation. eLife. doi:10.7554/eLife.60824 -- Materials
        and methods, "Neural recordings in cortex": the crossover of the gamma and
        alpha-beta relative power profiles as the estimate of layer 4, which
        ``crossover_contact`` reports. The paper gives no normalization for it beyond citing
        Bastos et al. (2018), and describes no acceptance test; :func:`vflip` rejects a fit
        whose support score is below `min_support_score`.
        Welch, P. D. (1967). The use of fast Fourier transform for the estimation of power
        spectra. IEEE Trans. Audio Electroacoust. doi:10.1109/TAU.1967.1161901
        -- the spectrum as the average of windowed periodograms over overlapping segments.
    """
    # 1. Validate inputs
    fs = float(fs)
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive and finite (Hz), got {fs}")

    _refuse_a_deep_first_declaration(orientation, depth_axis, shallow_end, "vflip_from_lfp")
    lfp_arr = np.asarray(lfp, dtype=np.float64)
    if lfp_arr.ndim != 2:
        raise ValueError(f"lfp must be a 2D array of shape (n_channels, n_times), got ndim={lfp_arr.ndim}")

    n_channels, n_times = lfp_arr.shape
    if n_times == 0:
        raise ValueError("lfp has zero time samples")

    # 2. Welch segment parameters
    eff_nperseg = int(min(n_times, int(fs))) if nperseg is None else int(nperseg)
    # A segment of n samples gives n // 2 + 1 one-sided bins.
    min_nperseg = 2 * (_MIN_FREQ_BINS - 1)
    if not min_nperseg <= eff_nperseg <= n_times:
        source = (
            f" from the default min(n_times, int(fs)) at fs={fs} Hz; pass nperseg"
            if nperseg is None else ""
        )
        raise ValueError(
            f"vflip_from_lfp: nperseg must be from {min_nperseg} to the {n_times} time samples "
            f"(vflip needs {_MIN_FREQ_BINS} frequency bins), got {eff_nperseg}{source}"
        )

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
        depth_axis=depth_axis,
        shallow_end=shallow_end,
    )
