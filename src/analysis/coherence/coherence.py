"""
coherence.py
============
Core functions for LFP-to-LFP coherence analysis between brain areas.
"""

import numpy as np
import pandas as pd
import scipy.signal as signal
from src.analysis.io.logger import log

def get_responsive_channels(metadata_csv: str) -> pd.DataFrame:
    """
    Read unit metadata and identify channels recording stable units that
    are significantly responsive (group != 'null').
    """
    df = pd.read_csv(metadata_csv)
    # Filter stable and responsive
    stable_resp = df[df["is_stable"] & (df["group"] != "null")].copy()
    if len(stable_resp) == 0:
        return pd.DataFrame(columns=["session_id", "peak_channel_global", "area", "layer", "group"])
        
    grouped = stable_resp.groupby(["session_id", "peak_channel_global"]).agg({
        "area": "first",
        "layer": "first",
        "group": "first"
    }).reset_index()
    
    return grouped

def compute_spectral_coherence(x: np.ndarray, y: np.ndarray, fs: float = 1000.0) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes magnitude-squared coherence between two 1D LFP signals.
    x, y: 1D arrays of the same length
    Returns: (frequencies, coherence_values)
    """
    # Using scipy's coherence function
    f, cxy = signal.coherence(x, y, fs=fs, nperseg=256, noverlap=128)
    return f, cxy
