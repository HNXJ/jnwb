from __future__ import annotations
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List

from src.analysis.io.loader import DataLoader
from src.analysis.lfp.lfp_constants import ALL_CONDITIONS, CANONICAL_AREAS
from src.analysis.io.logger import log

def get_lfp_signal(
    area: str,
    condition: str,
    align_to: str = 'omission',
    allow_channel_trim: bool = False,
    **kwargs
) -> np.ndarray:
    """
    Public entrypoint for LFP signal access.
    Uses DataLoader and ensures omission-local alignment where applicable.
    Returns: Concatenated array (total_trials, area_channels, time)
    """
    loader = DataLoader()

    # Standardize condition
    if condition not in ALL_CONDITIONS:
        log.warning(f"Condition {condition} not in canonical set.")

    # Determine alignment
    # If align_to is 'omission', DataLoader handles the cropping
    data_list = loader.get_signal(mode="lfp", condition=condition, area=area, align_to=align_to, **kwargs)

    if not data_list:
        return np.array([])

    # Concatenate trials across sessions
    # data_list entries are (trials, area_channels, time)

    # Task 3: Explicit Channel Trimming Policy
    ch_counts = [arr.shape[1] for arr in data_list]
    min_ch = min(ch_counts)
    max_ch = max(ch_counts)

    if min_ch != max_ch:
        if not allow_channel_trim:
            raise ValueError(f"Mismatched channel counts for area {area}: {ch_counts}. "
                             f"Set allow_channel_trim=True to proceed with {min_ch} channels.")

        log.warning(f"TRIMMING CHANNELS for area {area} across {len(data_list)} session-entries. "
                    f"Counts: {ch_counts} -> {min_ch}. "
                    f"Warning: Laminar/depth interpretation may be affected by data loss on probes with {max_ch} channels.")

    aligned_data = [arr[:, :min_ch, :] for arr in data_list]

    final_arr = np.concatenate(aligned_data, axis=0)
    return final_arr

def run_lfp_spectral_pipeline(area: str, condition: str, allow_channel_trim: bool = False):
    """
    Complete flow: Load -> Preprocess -> TFR -> Normalize -> Band Collapse
    """
    from src.analysis.lfp.lfp_preproc import preprocess_lfp, baseline_normalize
    from src.analysis.lfp.lfp_tfr import compute_multitaper_tfr, collapse_band_power

    # 1. Load aligned to omission
    log.progress(f"Running Spectral Pipeline for {area} - {condition}")
    lfp = get_lfp_signal(area, condition, align_to="omission", pre_ms=2000, post_ms=2000, allow_channel_trim=allow_channel_trim)
    if lfp.size == 0: return None

    # 2. Preprocess
    lfp_clean = preprocess_lfp(lfp)

    # 3. TFR (Linear Power)
    # Using efficient band power calculation to save memory
    from src.analysis.lfp.lfp_tfr import compute_band_power_efficiently, compute_multitaper_tfr

    freqs, times, band_dict = compute_band_power_efficiently(lfp_clean)
    times_local = times - 2000.0

    # Also get a summary TFR Heatmap (averaged across trials/channels early to save memory)
    # We'll just compute a single-trial-like TFR for the summary plot if needed,
    # but run_lfp_spectral_pipeline usually returns everything.
    # To be efficient, let's just compute the average TFR directly.

    # 4. Average across trials and channels for pop summary
    # We'll re-calculate TFR on averaged data for the heatmap to be super efficient
    avg_lfp = np.mean(lfp_clean, axis=(0, 1), keepdims=True)
    f_sum, t_sum, p_sum = compute_multitaper_tfr(avg_lfp)
    # p_sum shape is (1, 1, freqs, times)

    # Baseline Normalize the summary TFR (dB)
    t_sum_local = t_sum - 2000.0 # Align to omission
    p_sum_db = baseline_normalize(p_sum[0, 0], t_sum_local, baseline_window=(-1000, -500))

    return {
        "freqs": freqs,
        "times": times_local,
        "tfr": p_sum_db,
        "bands": {k: np.mean(v, axis=(0, 1)) for k, v in band_dict.items()},
        "bands_full": band_dict # {band_name: (trials, channels, times)}
    }
