"""Population trajectory analysis using GPU-accelerated SVD (PCA).

Provides dimensionality reduction (PCA) via Singular Value Decomposition (SVD)
to track and visualize population trajectories over time.
Supports PyTorch for GPU acceleration if available.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from ._backend import CPU, CUDA, resolve_device, warn_device_fallback
from ._bins import bin_edges, right_open_counts, whole_bin_count
from .gpu_pca import pin_component_signs

log = logging.getLogger(__name__)



def build_time_resolved_matrix(
    session,
    area: str,
    epochs_df: pd.DataFrame,
    time_window_ms: Tuple[float, float] = (-1000.0, 2000.0),
    bin_size_ms: float = 20.0,
    quality: Optional[str] = None
) -> Tuple[np.ndarray, List[int], np.ndarray]:
    """
    Build a trial-by-trial time-resolved population spike count matrix.

    Args:
        session: Generic session container or interface providing get_units() and get_spike_times()
        area: Brain area to select units from
        epochs_df: DataFrame of trials/epochs (must have 'start_time')
        time_window_ms: (start_ms, end_ms) relative to epoch onset. Its span must be a whole
            number of ``bin_size_ms`` bins. Every bin is right-open, as in
            :func:`jnwb.bin_spikes`, so a spike on ``end_ms`` is outside the window.
        bin_size_ms: Width of time bins in ms
        quality: Filter units by quality tier ('stable_plus', 'stable', etc.)

    Returns:
        X: Feature matrix of shape (n_trials, n_units, n_bins)
        unit_ids: List of unit identities (raw units_df row-index positions, matching
            the session's get_spike_times primary lookup convention) represented in the rows/columns of X
        bin_centers: Center times of bins relative to trial onset in ms

    Raises:
        ValueError: If the span of ``time_window_ms`` is not a whole multiple of
            ``bin_size_ms``; the message names the nearest valid windows.
    """
    n_bins = whole_bin_count(time_window_ms, bin_size_ms, "build_time_resolved_matrix",
                             "time_window_ms")
    start_sec = time_window_ms[0] / 1000.0
    end_sec = time_window_ms[1] / 1000.0
    bin_sec = bin_size_ms / 1000.0
    bin_centers = (bin_edges(start_sec, bin_sec, n_bins)[:-1] + bin_sec / 2.0) * 1000.0

    units_df = session.get_units(quality=quality, area=area)
    if len(units_df) == 0:
        log.warning(f"No units found in area {area}")
        return np.zeros((len(epochs_df), 0, n_bins)), [], bin_centers

    # Unit identity is the raw units_df row position (units_df.index), not the 'unit_id' column:
    # kilosort cluster ids can have gaps relative to row order, while get_spike_times indexes by
    # row position. Passing the 'unit_id' column misattributes spike trains when ids are non-contiguous.
    unit_ids = units_df.index.tolist()
    n_trials = len(epochs_df)
    n_units = len(unit_ids)



    X = np.zeros((n_trials, n_units, n_bins))
    onsets = epochs_df['start_time'].values

    for j, unit_id in enumerate(unit_ids):
        spike_times = session.get_spike_times(unit_id)
        if len(spike_times) == 0:
            continue
        # The same right-open bins as `bin_spikes`: a spike on the window end is outside.
        st = np.asarray(spike_times, dtype=float)
        X[:, j, :] = right_open_counts((st - onset for onset in onsets),
                                       start_sec, end_sec, bin_sec, n_bins)

    return X, unit_ids, bin_centers


def compute_population_trajectory(
    session,
    area: str,
    epochs_df: pd.DataFrame,
    time_window_ms: Tuple[float, float] = (-1000.0, 2000.0),
    bin_size_ms: float = 20.0,
    n_components: int = 3,
    quality: Optional[str] = None,
    device: str = 'cpu'
) -> Dict[str, Union[np.ndarray, List[int], float]]:
    """
    Compute population trajectory using standardized correlation PCA (SVD).
    Supports GPU SVD acceleration via PyTorch if device='cuda' and CUDA is available.

    .. note::
        This function computes standardized PCA (correlation PCA): features across units
        are centered and z-scored to unit variance before SVD. Units contribute equally
        to total variance regardless of baseline firing rate. This contrasts with
        :meth:`jnwb.analyzers.UnitAnalyzer.population_trajectory` which computes
        unstandardized covariance PCA (centering only).

    Args:
        session: session object exposing ``get_units`` and ``get_spike_times``
        area: Brain area to decode from
        epochs_df: DataFrame of trials/epochs (must have 'start_time')
        time_window_ms: Time window in ms relative to onset
        bin_size_ms: Width of time bins in ms
        n_components: Number of PCA components to keep
        quality: Filter units by quality tier
        device: 'cpu' or 'cuda' (GPU acceleration)

    Returns:
        Dict with:
        - trajectory: (n_trials, n_components, n_bins) projected coordinates
        - explained_variance: explained variance ratio of kept components
        - unit_ids: unit IDs in analysis
        - bin_centers: center times of bins
        - device_used: 'cpu' or 'cuda', the device that performed the SVD
    """
    X, unit_ids, bin_centers = build_time_resolved_matrix(
        session, area, epochs_df, time_window_ms, bin_size_ms, quality
    )

    n_trials, n_units, n_bins = X.shape
    if n_units == 0 or n_trials == 0:
        # An explicitly requested population with no observations has no trajectory, and
        # zeros are a point in state space like any other: a caller plotting the result
        # saw a population sitting at the origin, and `explained_variance == 0.0` reads as
        # "PCA ran and explained nothing" rather than "PCA did not run". `TFRAnalyzer`
        # already answers NaN for the same condition. Zero stays valid only where zero was
        # estimated from observations.
        return {
            'trajectory': np.full((n_trials, n_components, n_bins), np.nan),
            'explained_variance': float('nan'),
            'unit_ids': [],
            'bin_centers': bin_centers
        }

    # Reshape X to (n_trials * n_bins, n_units) to perform PCA over the unit dimension
    X_flat = X.transpose(0, 2, 1).reshape(n_trials * n_bins, n_units)
    
    # Scale and center features
    mean = np.mean(X_flat, axis=0, keepdims=True)
    std = np.std(X_flat, axis=0, keepdims=True)
    std[std == 0.0] = 1.0
    X_scaled = (X_flat - mean) / std

    actual_components = min(n_components, X_flat.shape[0], n_units)

    def _svd_numpy():
        U, S, Vt = np.linalg.svd(X_scaled, full_matrices=False)
        proj = X_scaled @ Vt[:actual_components, :].T
        return proj, Vt[:actual_components, :], S

    resolved = resolve_device(device, context="compute_population_trajectory", prefer="torch", stacklevel=3)

    # Run SVD
    if resolved == CUDA:
        try:
            import torch
            X_tensor = torch.as_tensor(X_scaled, device="cuda")
            if not X_tensor.is_floating_point():
                X_tensor = X_tensor.to(torch.float64)
            U, S, V = torch.linalg.svd(X_tensor, full_matrices=False)
            V_top = V[:actual_components, :]  # (actual_components, n_units)
            proj = X_tensor @ V_top.t()
            proj_np = proj.cpu().numpy()
            S_np = S.cpu().numpy()
            V_np = V_top.cpu().numpy()
        except Exception as e:
            warn_device_fallback("compute_population_trajectory", e, stacklevel=3)
            log.warning(f"PyTorch SVD failed: {e}. Falling back to NumPy SVD.")
            resolved = CPU
            proj_np, V_np, S_np = _svd_numpy()
    else:
        proj_np, V_np, S_np = _svd_numpy()

    # Both branches already agree to 1e-13 in float64; what differed was the sign LAPACK
    # and cuSOLVER happened to pick, which showed up as a trajectory reflected through
    # the origin. See :func:`jnwb.gpu_pca.pin_component_signs`.
    V_np, proj_np = pin_component_signs(V_np, proj_np)

    # Calculate variance explained ratio
    total_var = np.sum(S_np ** 2)
    # No total variance means no ratio, not a ratio of zero.
    explained_variance = (
        np.sum(S_np[:actual_components] ** 2) / total_var if total_var > 0.0 else np.nan
    )

    # If requested n_components > actual_components, pad projection along component axis
    if actual_components < n_components:
        # These components do not exist -- there were not enough units or samples to
        # estimate them. Zero-padding made them indistinguishable from a component whose
        # projection was measured to be zero.
        pad_width = ((0, 0), (0, n_components - actual_components))
        proj_np = np.pad(proj_np, pad_width, mode="constant", constant_values=np.nan)

    # Reshape projected trajectories back to (n_trials, n_components, n_bins)
    trajectory = proj_np.reshape(n_trials, n_bins, n_components).transpose(0, 2, 1)

    return {
        'trajectory': trajectory,
        'explained_variance': float(explained_variance),
        'unit_ids': unit_ids,
        'bin_centers': bin_centers,
        'device_used': resolved,
    }
