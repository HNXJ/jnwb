"""
spsam_pipeline.py — Core primitives for Spike-Phase-LFP Analysis Module (SpSAM).

Provides:
  - map_group_to_lfp_key(): probe name → (lfp_acquisition_key, probe_idx)
  - parse_probe_areas(): electrode location string → per-channel area labels
  - build_channel_area_map(): electrodes DataFrame → global_ch_idx → {area, local_idx, probe_id}
  - extract_lfp_phase(): bandpass filter + Hilbert on LFP segment
  - compute_plv(): Phase-Locking Value from phase array and spike binary
  - compute_cross_correlation(): Pearson cross-correlation at lag-0

All functions are probe-agnostic and work on pre-loaded numpy arrays.
"""
import re
import numpy as np
import scipy.signal as signal
from src.analysis.io.logger import log


# ---------------------------------------------------------------------------
# Probe / LFP key mapping
# ---------------------------------------------------------------------------

def map_group_to_lfp_key(name: str) -> tuple[str, int]:
    """Map electrode group name → (lfp_acquisition_key, probe_idx).

    Handles 'probeA'/'a'/0 → probe_0_lfp, idx=0, etc.
    Falls back to probe_0_lfp, idx=0 on unknown names.
    """
    n = str(name).lower().strip()
    if "probea" in n or n in ("a", "0"):
        return "probe_0_lfp", 0
    if "probeb" in n or n in ("b", "1"):
        return "probe_1_lfp", 1
    if "probec" in n or n in ("c", "2"):
        return "probe_2_lfp", 2
    log.warning(f"UNKNOWN_PROBE_NAME: {name!r}. Defaulting to probe_0_lfp.")
    return "probe_0_lfp", 0


# ---------------------------------------------------------------------------
# Channel → Area mapping (uses electrodes table 'location' column)
# ---------------------------------------------------------------------------

def parse_location_to_areas(location_str: str) -> list[str]:
    """Parse a location string like 'V4, MT' or 'PFC' into a list of area tokens."""
    raw = str(location_str).strip()
    # Split on comma or semicolon
    if "," in raw:
        parts = [p.strip() for p in raw.split(",")]
    elif ";" in raw:
        parts = [p.strip() for p in raw.split(";")]
    else:
        parts = [raw] if raw else ["unresolved"]
    return [p for p in parts if p]


def build_channel_area_map(elec_df) -> dict:
    """Build a dict: global_channel_idx → {area, local_idx, probe_id, probe_name}.

    Uses the electrodes DataFrame with columns: location, group_name, probe.
    The global channel index is the row index of the electrodes table.
    The local channel index is computed within each probe's contiguous block.

    For probes with multiple areas in their location (e.g. 'V4, MT'), we split
    the 128-channel block into equal halves, first area = lower channels.
    """
    # Group probes by group_name, preserving insertion order
    probe_groups = {}
    for global_idx, row in elec_df.iterrows():
        g_name = row.get("group_name", row.get("probe", "probeA"))
        if g_name not in probe_groups:
            probe_groups[g_name] = []
        probe_groups[g_name].append(global_idx)

    channel_area_map = {}

    for probe_idx, (p_name, ch_global_list) in enumerate(probe_groups.items()):
        n_ch = len(ch_global_list)
        # Get the location for this probe (same for all electrodes in the group)
        loc_str = elec_df.loc[ch_global_list[0], "location"]
        areas = parse_location_to_areas(loc_str)
        n_areas = len(areas)

        # Build per-channel area assignment
        if n_areas == 1:
            ch_areas = [areas[0]] * n_ch
        elif n_areas == 2:
            half = n_ch // 2
            ch_areas = [areas[0]] * half + [areas[1]] * (n_ch - half)
        else:
            log.warning(
                f"NONSTANDARD_PROBE_AREA_MAPPING: Probe {p_name} has "
                f"{n_areas} areas: {areas}. Splitting evenly."
            )
            base_size = n_ch // n_areas
            rem = n_ch % n_areas
            ch_areas = []
            for i, area in enumerate(areas):
                size = base_size + (1 if i < rem else 0)
                ch_areas.extend([area] * size)

        _, probe_idx_key = map_group_to_lfp_key(p_name)

        for local_idx, global_idx in enumerate(ch_global_list):
            channel_area_map[global_idx] = {
                "probe_name": p_name,
                "probe_id": probe_idx_key,
                "local_idx": local_idx,
                "area": ch_areas[local_idx] if local_idx < len(ch_areas) else "unresolved",
            }

    return channel_area_map


# ---------------------------------------------------------------------------
# Legacy compatibility shim (used by run_spsam_pipeline.py)
# ---------------------------------------------------------------------------

def parse_probe_areas(area_string: str, num_channels: int = 128) -> tuple[list, list]:
    """Parse a raw area string into (areas_list, per_channel_area_list).
    DEPRECATED: prefer build_channel_area_map with the full electrodes DataFrame.
    """
    raw_desc = str(area_string).strip()
    if "," in raw_desc or ";" in raw_desc or "/" in raw_desc:
        delim = "," if "," in raw_desc else (";" if ";" in raw_desc else "/")
        areas = [a.strip() for a in raw_desc.split(delim)]
    else:
        areas = [raw_desc] if raw_desc else ["unresolved"]

    n_areas = len(areas)
    channels_area: list[str] = []

    if n_areas == 1:
        channels_area = [areas[0]] * num_channels
    elif n_areas == 2:
        channels_area = [areas[0]] * 64 + [areas[1]] * 64
    else:
        log.warning(
            f"NONSTANDARD_PROBE_AREA_MAPPING: Probe has {n_areas} areas: {areas}. Splitting evenly."
        )
        base_size = num_channels // n_areas
        rem = num_channels % n_areas
        for idx, area in enumerate(areas):
            size = base_size + (1 if idx < rem else 0)
            channels_area.extend([area] * size)

    return areas, channels_area


# ---------------------------------------------------------------------------
# Frequency-domain coupling
# ---------------------------------------------------------------------------

def extract_lfp_phase(lfp_data: np.ndarray, freq_band: tuple, fs: float = 1000.0) -> np.ndarray:
    """Bandpass-filter LFP and return instantaneous phase via Hilbert transform.

    Args:
        lfp_data: 1-D or 2-D array (..., time). Filtered along last axis.
        freq_band: (low_hz, high_hz).
        fs: sampling frequency in Hz.

    Returns:
        Phase array same shape as lfp_data.
    """
    nyq = 0.5 * fs
    low, high = freq_band[0] / nyq, freq_band[1] / nyq
    # Clamp to valid range
    low = max(low, 1e-4)
    high = min(high, 0.9999)
    b, a = signal.butter(4, [low, high], btype="bandpass")
    filtered = signal.filtfilt(b, a, lfp_data, axis=-1)
    analytic = signal.hilbert(filtered, axis=-1)
    return np.angle(analytic)


def compute_plv(phase_lfp: np.ndarray, spikes: np.ndarray) -> float:
    """Compute Phase-Locking Value.

    Args:
        phase_lfp: shape (n_trials, time) — LFP phase at each sample.
        spikes: shape (n_trials, time) — binary spike count per sample.

    Returns:
        PLV scalar in [0, 1].
    """
    spike_mask = spikes > 0
    spike_phases = phase_lfp[spike_mask]
    if len(spike_phases) == 0:
        return 0.0
    return float(np.abs(np.mean(np.exp(1j * spike_phases))))


# ---------------------------------------------------------------------------
# Time-domain coupling
# ---------------------------------------------------------------------------

def compute_cross_correlation(lfp_data: np.ndarray, spikes_data: np.ndarray) -> float:
    """Compute Pearson correlation at lag-0 between flattened spike and LFP arrays.

    Args:
        lfp_data: shape (n_trials, time).
        spikes_data: shape (n_trials, time).

    Returns:
        Pearson r, or 0.0 if either series has zero variance.
    """
    spk_flat = spikes_data.flatten().astype(float)
    lfp_flat = lfp_data.flatten().astype(float)
    if np.std(spk_flat) == 0.0 or np.std(lfp_flat) == 0.0:
        return 0.0
    return float(np.corrcoef(spk_flat, lfp_flat)[0, 1])
