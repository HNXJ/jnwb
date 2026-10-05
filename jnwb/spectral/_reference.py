"""Re-referencing along a shaft: bipolar, Laplacian, voltage curvature and current source density."""

from typing import Optional
import numpy as np
from .._layout import require_channel_major


def _require_channel_permutation(
    channel_order: np.ndarray, n_channels: int, func_name: str
) -> np.ndarray:
    """Return ``channel_order`` as an index array, rejecting anything but a permutation.

    A short, long, or duplicated order silently dropped channels in ``bipolar_reference``
    and left rows of ``laplacian_reference``'s output unwritten, so the function returned
    whatever ``np.empty_like`` had been handed: two identical calls did not agree, and the
    uninitialised values (order 1e-297) are not distinguishable from a measured amplitude.
    """
    order = np.asarray(channel_order)
    if order.ndim != 1:
        raise ValueError(
            f"{func_name}: channel_order must be 1-D, got shape {order.shape}."
        )
    if not np.issubdtype(order.dtype, np.integer):
        raise ValueError(
            f"{func_name}: channel_order must be an integer index array, got dtype {order.dtype}."
        )
    if order.shape[0] != n_channels:
        raise ValueError(
            f"{func_name}: channel_order has {order.shape[0]} entries for {n_channels} "
            "channels; it must name every channel exactly once."
        )
    if not np.array_equal(np.sort(order), np.arange(n_channels)):
        raise ValueError(
            f"{func_name}: channel_order must be a permutation of range({n_channels}); "
            f"got {np.array2string(order, threshold=16)}. Repeated or out-of-range "
            "indices drop channels and leave the output partly uninitialised."
        )
    return order


def bipolar_reference(channel_data: np.ndarray, channel_order: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Bipolar (adjacent-channel difference) re-reference along a probe's depth order.

    Each output channel i is ``data[order[i+1]] - data[order[i]]``, so a common
    signal present identically on adjacent contacts (shared reference, distant
    volume-conducted source) cancels; a genuine local generator does not.
    Output has one fewer channel than the input.

    Args:
        channel_data: (n_channels, n_samples) array, one row per electrode contact.
        channel_order: optional (n_channels,) index array giving depth order
            (shallow to deep or vice versa); defaults to row order as given.

    Returns:
        (n_channels - 1, n_samples) bipolar-referenced array.

    References:
        Bastos, A. M., et al. (2020). Layer and rhythm specificity for predictive routing.
        PNAS. doi:10.1073/pnas.2014868117 -- Experimental Procedures, "Local Field Potential
        Power, Coherence, and Granger Causality Analysis": sample-by-sample bipolar
        differences taken before coherence and Granger causality, because a common
        reference can make both spurious. The paper subtracts contacts 400 um apart; this
        function subtracts adjacent contacts.
    """
    channel_data = np.asarray(channel_data, dtype=float)
    if channel_data.ndim != 2:
        raise ValueError(f"channel_data must be 2D (n_channels, n_samples), got shape {channel_data.shape}")
    order = (
        np.arange(channel_data.shape[0])
        if channel_order is None
        else _require_channel_permutation(
            channel_order, channel_data.shape[0], "bipolar_reference"
        )
    )
    ordered = channel_data[order]
    return ordered[1:] - ordered[:-1]


def laplacian_reference(channel_data: np.ndarray, channel_order: Optional[np.ndarray] = None) -> np.ndarray:
    """
    1D nearest-neighbor Laplacian re-reference along a probe's depth order.

    Each interior output channel i is ``data[order[i]] - mean(data[order[i-1]], data[order[i+1]])``.
    Like ``bipolar_reference``, this cancels signal shared identically across
    neighboring contacts (shared reference / distant volume conduction) while
    preserving a source local to one contact. Edge channels (first/last in
    ``channel_order``) use their single available neighbor instead of a two-
    neighbor mean.

    Args:
        channel_data: (n_channels, n_samples) array, one row per electrode contact.
        channel_order: optional (n_channels,) index array giving depth order;
            defaults to row order as given.

    Returns:
        (n_channels, n_samples) Laplacian-referenced array, same channel count
        as input (unlike ``bipolar_reference``, which drops one channel).

    Raises:
        ValueError: If ``channel_data`` is not 2-D, has fewer than 2 channels, or
            ``channel_order`` is not a permutation of ``range(n_channels)``.
    """
    channel_data = np.asarray(channel_data, dtype=float)
    if channel_data.ndim != 2:
        raise ValueError(f"channel_data must be 2D (n_channels, n_samples), got shape {channel_data.shape}")
    order = (
        np.arange(channel_data.shape[0])
        if channel_order is None
        else _require_channel_permutation(
            channel_order, channel_data.shape[0], "laplacian_reference"
        )
    )
    ordered = channel_data[order]
    n_ch = ordered.shape[0]
    if n_ch < 2:
        # A single contact has no neighbour; this returned the channel minus itself (zeros).
        raise ValueError(f"laplacian_reference needs at least 2 channels, got {n_ch}")
    out = np.empty_like(ordered)
    for i in range(n_ch):
        if i == 0:
            neighbor_mean = ordered[1] if n_ch > 1 else ordered[0]
        elif i == n_ch - 1:
            neighbor_mean = ordered[i - 1]
        else:
            neighbor_mean = 0.5 * (ordered[i - 1] + ordered[i + 1])
        out[i] = ordered[i] - neighbor_mean
    # Result is in `order` order; un-permute back to original channel positions.
    result = np.empty_like(out)
    result[order] = out
    return result


def voltage_curvature_1d(
    lfp_matrix: np.ndarray,
    pitch_um: float,
    axis: int = 0,
) -> np.ndarray:
    """Compute the discrete second spatial derivative of extracellular potential along a laminar probe.

    Estimates spatial voltage curvature (Nicholson & Freeman, 1975):
        Curvature(z_i) = (V[i+1] - 2*V[i] + V[i-1]) / (pitch_um * 1e-6)^2

    Important Scientific Distinction:
        Voltage curvature is the purely electrical second derivative (in V/m^2 when potential is in Volts).
        It does NOT assume a tissue conductivity tensor and is NOT physical Current Source Density (CSD).
        To compute physical CSD in A/m^3, call ``current_source_density_1d(..., conductivity_s_per_m=...)``.

    Args:
        lfp_matrix: 2D array of continuous local field potentials in Volts (V),
            with shape (n_channels, n_times) when axis=0. Minimum 3 channels required.
        pitch_um: Inter-contact spacing (electrode pitch) in micrometers (um). Must be strictly positive.
        axis: Spatial/channel axis along which to take the second derivative (default: 0).

    Returns:
        Curvature array in V/m^2 with 2 fewer channels along `axis` than `lfp_matrix`
        (interior channels 1 to N-2).

    Raises:
        ValueError: If `pitch_um <= 0` or number of channels along `axis` is less than 3.

    References:
        Nicholson, C., & Freeman, J. A. (1975). Theory of current source-density analysis
        and determination of conductivity tensor for anuran cerebellum. J. Neurophysiol.
        doi:10.1152/jn.1975.38.2.356 -- the second spatial derivative of the potential
        that current source density scales by -sigma, here as the three-point difference.
    """
    if pitch_um <= 0:
        raise ValueError(f"Electrode pitch must be strictly positive; got {pitch_um} um.")
    arr = np.asarray(lfp_matrix, dtype=float)
    # Before the count is read as a contact count, check it can be one. `bandpass_filter`
    # defaults axis=-1 and this function defaults axis=0, so the obvious two-call chain hands
    # the second derivative a time axis and neither call raised.
    require_channel_major(
        arr, axis, "voltage_curvature_1d", pitch_um=pitch_um, argument="lfp_matrix"
    )
    n_ch = arr.shape[axis]
    if n_ch < 3:
        raise ValueError(f"Voltage curvature requires at least 3 channels along spatial axis; got {n_ch}.")

    pitch_m = pitch_um * 1e-6
    delta_z2 = pitch_m ** 2

    # Second spatial difference: (V[i+1] - 2*V[i] + V[i-1]) / delta_z2
    sl_prev = [slice(None)] * arr.ndim
    sl_curr = [slice(None)] * arr.ndim
    sl_next = [slice(None)] * arr.ndim

    sl_prev[axis] = slice(0, n_ch - 2)
    sl_curr[axis] = slice(1, n_ch - 1)
    sl_next[axis] = slice(2, n_ch)

    d2v = (arr[tuple(sl_next)] - 2.0 * arr[tuple(sl_curr)] + arr[tuple(sl_prev)]) / delta_z2
    return d2v


def current_source_density_1d(
    lfp_matrix: np.ndarray,
    pitch_um: float,
    conductivity_s_per_m: float,
    axis: int = 0,
) -> np.ndarray:
    """Compute physical 1D Current Source Density (CSD) along a laminar electrode array.

    Physical CSD models transmembrane current sources and sinks per unit volume via Poisson's equation
    in an assumed isotropic, homogeneous extracellular medium:
        CSD(z_i) = -sigma * d^2V / dz^2
                 ≈ -conductivity_s_per_m * (V[i+1] - 2*V[i] + V[i-1]) / (pitch_um * 1e-6)^2

    Sign Convention:
        - Negative values indicate a CURRENT SINK (inward transmembrane current, e.g. excitatory synaptic input).
        - Positive values indicate a CURRENT SOURCE (outward passive/return current).

    Dimensional Invariant:
        Potential V must be in Volts (V).
        Pitch must be in micrometers (um, converted to m).
        Conductivity must be explicitly supplied in Siemens per meter (S/m).
        Output is returned in SI physical units: Amperes per cubic meter (A/m^3).
        (Note: 1 A/m^3 = 10^-3 uA/mm^3 = 1 nA/mm^3).

    Args:
        lfp_matrix: 2D array of continuous local field potentials in Volts (V),
            with shape (n_channels, n_times) when axis=0. Minimum 3 channels required.
        pitch_um: Inter-contact spacing in micrometers (um). Must be strictly positive.
        conductivity_s_per_m: Extracellular tissue conductivity in S/m (e.g. 0.3 to 0.4 S/m in mammalian cortex).
            Required argument; never defaulted. Must be strictly positive.
        axis: Spatial/channel axis along probe depth (default: 0).

    Returns:
        Array of physical Current Source Density in A/m^3, with 2 fewer channels along `axis`.

    Raises:
        ValueError: If `pitch_um <= 0`, `conductivity_s_per_m <= 0`, or channel count < 3.

    References:
        Nicholson, C., & Freeman, J. A. (1975). Theory of current source-density analysis
        and determination of conductivity tensor for anuran cerebellum. J. Neurophysiol.
        doi:10.1152/jn.1975.38.2.356 -- current source density as -sigma times the second
        spatial derivative of the potential, in one dimension with homogeneous conductivity.
    """
    if conductivity_s_per_m <= 0:
        raise ValueError(
            f"Tissue conductivity must be strictly positive; got {conductivity_s_per_m} S/m. "
            "CSD is physically undefined without positive conductivity."
        )
    curvature = voltage_curvature_1d(lfp_matrix, pitch_um=pitch_um, axis=axis)
    return -conductivity_s_per_m * curvature
