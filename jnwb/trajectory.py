"""
Population Trajectory Analysis using GPU-Accelerated SVD (PCA)

Provides dimensionality reduction (PCA) via Singular Value Decomposition (SVD)
to track and visualize population trajectories over time.
Supports PyTorch for GPU acceleration if available.

Author: Antigravity
Date: 2026-07-04
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

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
        session: OmissionSession object
        area: Brain area to select units from
        epochs_df: DataFrame of trials/epochs (must have 'start_time')
        time_window_ms: (start_ms, end_ms) relative to epoch onset
        bin_size_ms: Width of time bins in ms
        quality: Filter units by quality tier ('stable_plus', 'stable', etc.)

    Returns:
        X: Feature matrix of shape (n_trials, n_units, n_bins)
        unit_ids: List of unit identities (raw units_df row-index positions, matching
            OmissionSession.get_spike_times's primary lookup convention -- NOT the
            per-probe-local 'unit_id' column) represented in the rows/columns of X
        bin_centers: Center times of bins relative to trial onset in ms
    """
    # Calculate bin edges
    start_sec = time_window_ms[0] / 1000.0
    end_sec = time_window_ms[1] / 1000.0
    bin_sec = bin_size_ms / 1000.0
    n_bins = int(round((end_sec - start_sec) / bin_sec))
    bin_edges = np.linspace(start_sec, end_sec, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0 * 1000.0

    units_df = session.get_units(quality=quality, area=area)
    if len(units_df) == 0:
        log.warning(f"No units found in area {area}")
        return np.zeros((len(epochs_df), 0, n_bins)), [], bin_centers

    # Identity convention (established in jnwb/session.py and used consistently across
    # jnwb.unit_classification, scripts/classify_units_shuffle_sso.py, etc.): unit identity
    # is the raw units_df row position (units_df.index), NOT the 'unit_id' DataFrame column.
    # 'unit_id' is a per-probe-local kilosort cluster id that can have gaps/resets relative to
    # the row index (filtered clusters), while OmissionSession.get_spike_times's PRIMARY lookup
    # is by row-index position. Passing the 'unit_id' column here silently fetched the WRONG
    # unit's real spike train whenever a session's kilosort ids have gaps -- confirmed on
    # sub-C31o_ses-230816_rec: PFC unit at row position 3 (unit_id column value 4.0) has 3470
    # real spikes, but get_spike_times(4.0) (the old buggy call) returned a different real
    # unit's 449-spike train (the one actually sitting at row-index 4). Using row-index
    # everywhere below avoids that silent misattribution.
    unit_ids = units_df.index.tolist()
    n_trials = len(epochs_df)
    n_units = len(unit_ids)



    X = np.zeros((n_trials, n_units, n_bins))
    onsets = epochs_df['start_time'].values

    for j, unit_id in enumerate(unit_ids):
        spike_times = session.get_spike_times(unit_id)
        if len(spike_times) == 0:
            continue
        # Sort spike times for searchsorted speed
        st = np.sort(spike_times)
        for i, onset in enumerate(onsets):
            # Map spike times to relative window
            rel_spikes = st - onset
            counts, _ = np.histogram(rel_spikes, bins=bin_edges)
            X[i, j, :] = counts

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
    Compute population trajectory using SVD/PCA.
    Supports GPU SVD acceleration via PyTorch if device='cuda' and CUDA is available.

    Args:
        session: OmissionSession object
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
    """
    X, unit_ids, bin_centers = build_time_resolved_matrix(
        session, area, epochs_df, time_window_ms, bin_size_ms, quality
    )

    n_trials, n_units, n_bins = X.shape
    if n_units == 0 or n_trials == 0:
        return {
            'trajectory': np.zeros((n_trials, n_components, n_bins)),
            'explained_variance': 0.0,
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

    # Run SVD
    if device == 'cuda':
        try:
            import torch
            if torch.cuda.is_available():
                X_tensor = torch.tensor(X_scaled, dtype=torch.float32, device='cuda')
                U, S, V = torch.linalg.svd(X_tensor, full_matrices=False)
                V_top = V[:n_components, :]  # (n_components, n_units)
                proj = X_tensor @ V_top.t()
                proj_np = proj.cpu().numpy()
                S_np = S.cpu().numpy()
            else:
                X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
                U, S, V = torch.linalg.svd(X_tensor, full_matrices=False)
                V_top = V[:n_components, :]
                proj = X_tensor @ V_top.t()
                proj_np = proj.numpy()
                S_np = S.numpy()
        except Exception as e:
            log.warning(f"PyTorch SVD failed: {e}. Falling back to NumPy SVD.")
            U, S, Vt = np.linalg.svd(X_scaled, full_matrices=False)
            proj_np = X_scaled @ Vt[:n_components, :].T
            S_np = S
    else:
        # NumPy CPU SVD
        U, S, Vt = np.linalg.svd(X_scaled, full_matrices=False)
        proj_np = X_scaled @ Vt[:n_components, :].T
        S_np = S

    # Calculate variance explained ratio
    total_var = np.sum(S_np ** 2)
    explained_variance = np.sum(S_np[:n_components] ** 2) / total_var if total_var > 0.0 else 0.0

    # Reshape projected trajectories back to (n_trials, n_components, n_bins)
    trajectory = proj_np.reshape(n_trials, n_bins, n_components).transpose(0, 2, 1)

    return {
        'trajectory': trajectory,
        'explained_variance': float(explained_variance),
        'unit_ids': unit_ids,
        'bin_centers': bin_centers
    }
