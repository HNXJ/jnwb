import os
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon, kruskal, spearmanr
from statsmodels.stats.multitest import multipletests
from typing import List, Tuple, Dict, Any


def compute_moving_spearman(spike_series: np.ndarray, lfp_series: np.ndarray, win_ms: int, step_ms: int, sampling_rate: float) -> Tuple[np.ndarray, np.ndarray]:
    """Compute moving Spearman correlation between two time series.

    Parameters
    ----------
    spike_series : np.ndarray
        1‑D array of spike counts or rates.
    lfp_series : np.ndarray
        1‑D array of LFP power values (same length as ``spike_series``).
    win_ms : int
        Window length in milliseconds.
    step_ms : int
        Step size in milliseconds.
    sampling_rate : float
        Samples per second of the input series.

    Returns
    -------
    times : np.ndarray
        Center time of each window (in seconds).
    corrs : np.ndarray
        Spearman correlation coefficient for each window.
    """
    if spike_series.shape != lfp_series.shape:
        raise ValueError("Series must have the same length")
    win_samples = int(win_ms * sampling_rate / 1000)
    step_samples = int(step_ms * sampling_rate / 1000)
    n = len(spike_series)
    corrs = []
    times = []
    for start in range(0, n - win_samples + 1, step_samples):
        end = start + win_samples
        rho, _ = spearmanr(spike_series[start:end], lfp_series[start:end])
        corrs.append(rho)
        times.append((start + end) / 2 / sampling_rate)
    return np.array(times), np.array(corrs)


def _run_contrast_test(data_a: np.ndarray, data_b: np.ndarray, test: str) -> Dict[str, Any]:
    """Run a single contrast test between two condition arrays.
    Supported tests: 'wilcoxon' (paired), 'kruskal' (independent).
    Returns a dict with statistic and p‑value.
    """
    if test == "wilcoxon":
        stat, p = wilcoxon(data_a, data_b)
    elif test == "kruskal":
        stat, p = kruskal(data_a, data_b)
    else:
        raise ValueError(f"Unsupported test: {test}")
    return {"statistic": stat, "p_value": p, "test": test}


def run_interarea_contrast(
    spike_data: Dict[Tuple[str, str], np.ndarray],
    lfp_data: Dict[Tuple[str, str], np.ndarray],
    condition_labels: np.ndarray,
    pairs: List[Tuple[str, str]],
    test: str = "wilcoxon",
) -> pd.DataFrame:
    """Contrast spike‑LFP interactions across area pairs.

    Parameters
    ----------
    spike_data : dict
        Mapping ``(area, unit)`` -> spike series.
    lfp_data : dict
        Mapping ``(area, probe)`` -> LFP series.
    condition_labels : np.ndarray
        Binary array (0 = control, 1 = omission) aligned to time series.
    pairs : list of tuple
        Each tuple ``(area_a, area_b)`` to contrast.
    test : str
        Statistical test to use.

    Returns
    -------
    pd.DataFrame
        Rows for each pair with statistic and corrected p‑value.
    """
    results = []
    for area_a, area_b in pairs:
        # Aggregate across units/probes for each area
        spikes_a = np.mean([spike_data[key] for key in spike_data if key[0] == area_a], axis=0)
        lfps_b = np.mean([lfp_data[key] for key in lfp_data if key[0] == area_b], axis=0)
        # Split by condition
        data_ctrl = spikes_a[condition_labels == 0]
        data_om = spikes_a[condition_labels == 1]
        res = _run_contrast_test(data_ctrl, data_om, test)
        results.append({"area_a": area_a, "area_b": area_b, **res})
    df = pd.DataFrame(results)
    # Multiple‑comparison correction
    if not df.empty:
        _, p_corr, _, _ = multipletests(df["p_value"].values, method="fdr_bh")
        df["p_fdr"] = p_corr
    return df


def run_interlayer_contrast(
    spike_data: Dict[Tuple[str, str, str], np.ndarray],
    lfp_data: Dict[Tuple[str, str, str], np.ndarray],
    condition_labels: np.ndarray,
    layers: List[Tuple[str, str]],
    test: str = "wilcoxon",
) -> pd.DataFrame:
    """Contrast within‑area, across‑layer interactions.
    ``layers`` is a list of ``(area, layer)`` tuples.
    """
    results = []
    for area, layer in layers:
        spikes = np.mean([spike_data[k] for k in spike_data if k[0] == area and k[2] == layer], axis=0)
        lfps = np.mean([lfp_data[k] for k in lfp_data if k[0] == area and k[2] == layer], axis=0)
        data_ctrl = spikes[condition_labels == 0]
        data_om = spikes[condition_labels == 1]
        res = _run_contrast_test(data_ctrl, data_om, test)
        results.append({"area": area, "layer": layer, **res})
    df = pd.DataFrame(results)
    if not df.empty:
        _, p_corr, _, _ = multipletests(df["p_value"].values, method="fdr_bh")
        df["p_fdr"] = p_corr
    return df

__all__ = [
    "compute_moving_spearman",
    "run_interarea_contrast",
    "run_interlayer_contrast",
]
