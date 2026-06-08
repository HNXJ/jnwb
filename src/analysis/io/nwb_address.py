"""Core NWB data-address layer for omission analysis.

Provides deterministic, reusable functions for:
1. Unit-neuron address book
2. LFP/probe/session address book
3. Event timing vectors by condition
4. Channel → area/layer mapping
5. Aligned signal extraction for selected units/channels/events

All functions use PyNWB read-only access. No NWB mutation.
"""

from __future__ import annotations

import datetime
import json
import warnings
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence, Optional
from collections import defaultdict

import numpy as np
import pandas as pd


# ============================================================================
# Constants
# ============================================================================

CANONICAL_CONDITIONS = [
    "AAAB", "AXAB", "AAXB", "AAAX",
    "BBBA", "BXBA", "BBXA", "BBBX",
    "RRRR", "RXRR", "RRXR", "RRRX",
]

CONDITION_NUMBER_MAP = {
    "AAAB": [1, 2],
    "AXAB": [3],
    "AAXB": [4],
    "AAAX": [5],
    "BBBA": [6, 7],
    "BXBA": [8],
    "BBXA": [9],
    "BBBX": [10],
    "RRRR": list(range(11, 27)),
    "RXRR": list(range(27, 35)),
    "RRXR": [35, 37, 39, 41],
    "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
}

NUMBER_TO_CONDITION: dict[int, str] = {}
for code, numbers in CONDITION_NUMBER_MAP.items():
    for number in numbers:
        NUMBER_TO_CONDITION[number] = code

BIN_WIDTH_MS = 5000  # 5 seconds for firing rate bins
BIN_WIDTH_S = 5.0

ALPHA_BETA_BAND = (8, 30)  # Hz
GAMMA_BAND = (32, 90)  # Hz


# ============================================================================
# Typed Blockers / Warnings
# ============================================================================

class NWBAddressWarning(UserWarning):
    """Warning for NWB address layer issues."""
    pass


def _warn(code: str, message: str) -> dict[str, Any]:
    """Create a warning record."""
    warnings.warn(f"[{code}] {message}", NWBAddressWarning)
    return {"code": code, "message": message}


# ============================================================================
# Helper: NWB Opening
# ============================================================================

def _open_nwb(nwb_path: str | Path) -> tuple[Any, Any, list[dict]]:
    """Open NWB file read-only. Returns (nwbfile, io_handle, warnings)."""
    path = Path(nwb_path)
    warns: list[dict] = []
    
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")
    
    try:
        from pynwb import NWBHDF5IO
    except ImportError as exc:
        raise ImportError(f"PyNWB not available: {exc}")
    
    try:
        io = NWBHDF5IO(str(path), "r", load_namespaces=True)
        nwbfile = io.read()
        return nwbfile, io, warns
    except Exception as exc:
        raise RuntimeError(f"BLOCKED_PYNWB_OPEN_FAILED: {type(exc).__name__}: {exc}")


# ============================================================================
# Function 1: Unit Address Book
# ============================================================================

def build_unit_address_book(
    nwb_paths: Iterable[str | Path],
    out_csv: str | Path | None = None,
    bin_ms: int = 5000,
    min_spikes_per_presence_bin: int = 1,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Build a unit-neuron address book from NWB files.
    
    Returns DataFrame with one row per unit/neuron.
    
    Required columns include:
    - general_unit_id: globally unique unit ID
    - subject_id, session_id: identifiers
    - unit_id_in_nwb, unit_row_index: NWB indexing
    - probe_id, electrode_group, area, area_status
    - peak_channel, peak_channel_local, peak_channel_global
    - firing rate stats (min, max, mean, median)
    - presence_ratio: fraction of bins with >= min_spikes_per_presence_bin
    """
    import hashlib
    
    path_list = [Path(p) for p in nwb_paths]
    rows: list[dict] = []
    
    for nwb_path in path_list:
        nwbfile, io, warns = _open_nwb(nwb_path)
        
        try:
            session_id = getattr(nwbfile, "session_id", nwb_path.stem)
            subject_id = getattr(nwbfile, "subject", None)
            if subject_id is not None:
                subject_id = getattr(subject_id, "subject_id", str(subject_id))
            else:
                # Parse from filename like sub-C31o_ses-230630_rec.nwb
                parts = nwb_path.stem.split("_")
                subject_id = parts[0] if parts else "unknown"
            
            nwb_size = nwb_path.stat().st_size
            
            # Get session timing
            session_start = getattr(nwbfile, "session_start_time", None)
            if session_start:
                session_start_s = 0.0  # Relative to session start
                # Get last spike time or acquisition data for session duration
                session_stop_s = None
            else:
                session_start_s = 0.0
                session_stop_s = None
            
            units_table = getattr(nwbfile, "units", None)
            if units_table is None or len(units_table) == 0:
                warns.append(_warn("NO_UNITS_TABLE", f"No units in {nwb_path.name}"))
                continue
            
            # Get electrodes table for channel mapping
            electrodes = getattr(nwbfile, "electrodes", None)
            
            # Bin width for firing rate calculation
            bin_s = bin_ms / 1000.0
            
            n_units = len(units_table)
            
            # Get column names available
            unit_cols = list(units_table.colnames)
            
            for unit_idx in range(n_units):
                row: dict[str, Any] = {
                    "subject_id": subject_id,
                    "session_id": session_id,
                    "nwb_file": str(nwb_path),
                    "nwb_file_name": nwb_path.name,
                    "nwb_size_bytes": nwb_size,
                    "unit_row_index": unit_idx,
                    "warnings": [],
                }
                
                # Get unit ID from table
                if "unit_id" in unit_cols:
                    uid_val = units_table["unit_id"][unit_idx]
                    row["unit_id_in_nwb"] = str(int(float(uid_val))) if uid_val is not None else f"unit_{unit_idx}"
                else:
                    row["unit_id_in_nwb"] = f"unit_{unit_idx}"
                
                # Get spike times for this unit
                spike_times_raw = units_table["spike_times"][unit_idx]
                if hasattr(spike_times_raw, "data"):
                    spike_times = np.asarray(spike_times_raw.data[:])
                else:
                    spike_times = np.asarray(spike_times_raw)
                n_spikes = len(spike_times)
                row["n_spikes_total"] = n_spikes
                
                # Session timing from spike times if not available elsewhere
                if n_spikes > 0:
                    spike_min = float(np.min(spike_times))
                    spike_max = float(np.max(spike_times))
                    if session_stop_s is None:
                        session_stop_s = spike_max
                else:
                    spike_min = 0.0
                    spike_max = 0.0
                    if session_stop_s is None:
                        session_stop_s = 0.0
                
                row["session_start_time_s"] = session_start_s
                row["session_stop_time_s"] = session_stop_s
                row["session_duration_s"] = session_stop_s - session_start_s
                
                # Compute firing rate bins
                row["bin_width_ms"] = bin_ms
                row["bin_width_s"] = bin_s
                
                if session_stop_s > session_start_s and n_spikes > 0:
                    n_bins = int(np.ceil((session_stop_s - session_start_s) / bin_s))
                    row["n_rate_bins"] = n_bins
                    
                    # Count spikes in each bin
                    bin_edges = np.arange(session_start_s, session_stop_s + bin_s, bin_s)
                    spike_counts, _ = np.histogram(spike_times, bins=bin_edges)
                    
                    # Firing rates per bin (Hz = spikes / seconds)
                    firing_rates = spike_counts / bin_s
                    
                    row["min_firing_rate_hz"] = float(np.min(firing_rates)) if len(firing_rates) > 0 else 0.0
                    row["max_firing_rate_hz"] = float(np.max(firing_rates)) if len(firing_rates) > 0 else 0.0
                    row["mean_firing_rate_hz"] = float(np.mean(firing_rates)) if len(firing_rates) > 0 else 0.0
                    row["median_firing_rate_hz"] = float(np.median(firing_rates)) if len(firing_rates) > 0 else 0.0
                    
                    # Presence ratio: bins with >= min_spikes
                    present_bins = np.sum(spike_counts >= min_spikes_per_presence_bin)
                    row["presence_ratio"] = present_bins / n_bins if n_bins > 0 else 0.0
                else:
                    row["n_rate_bins"] = 0
                    row["min_firing_rate_hz"] = 0.0
                    row["max_firing_rate_hz"] = 0.0
                    row["mean_firing_rate_hz"] = 0.0
                    row["median_firing_rate_hz"] = 0.0
                    row["presence_ratio"] = 0.0
                
                # Probe/electrode group resolution
                if "electrode_group" in unit_cols:
                    eg = units_table["electrode_group"][unit_idx]
                    row["electrode_group"] = str(eg)
                    # Try to extract probe_id from electrode_group name
                    eg_name = str(getattr(eg, "name", eg))
                    if "probe" in eg_name.lower():
                        # Parse probe number
                        import re
                        probe_match = re.search(r'probe[\s_]*(\d+)', eg_name, re.IGNORECASE)
                        if probe_match:
                            row["probe_id"] = int(probe_match.group(1))
                        else:
                            row["probe_id"] = eg_name
                    else:
                        row["probe_id"] = eg_name
                else:
                    row["electrode_group"] = "unresolved"
                    row["probe_id"] = "unresolved"
                
                # Peak channel resolution
                peak_channel = None
                peak_channel_status = "unresolved"
                
                # Try explicit peak_channel columns
                for col in ["peak_channel", "peak_channel_id", "electrode", "electrodes"]:
                    if col in unit_cols:
                        val = units_table[col][unit_idx]
                        if val is not None and not (isinstance(val, float) and np.isnan(val)):
                            peak_channel = int(float(val))
                            peak_channel_status = f"resolved_from_{col}"
                            break
                
                if peak_channel is not None:
                    row["peak_channel_global"] = peak_channel
                    # Convert to local channel if 128-channel probes
                    probe_id = row.get("probe_id")
                    if isinstance(probe_id, int) and peak_channel >= 0:
                        row["peak_channel_local"] = peak_channel % 128
                        row["peak_channel"] = row["peak_channel_local"]
                    else:
                        row["peak_channel_local"] = peak_channel
                        row["peak_channel"] = peak_channel
                    row["peak_channel_status"] = peak_channel_status
                else:
                    row["peak_channel"] = ""
                    row["peak_channel_local"] = ""
                    row["peak_channel_global"] = ""
                    row["peak_channel_status"] = "unresolved"
                
                # Area resolution
                area = "unresolved"
                area_status = "unresolved"
                
                # 1. Check unit-level area column
                if "area" in unit_cols:
                    val = units_table["area"][unit_idx]
                    if val is not None and str(val) != "nan":
                        area = str(val)
                        area_status = "unit_level"
                
                # 2. Check electrodes table via peak_channel
                if area == "unresolved" and peak_channel is not None and electrodes is not None:
                    if "location" in electrodes.colnames and peak_channel < len(electrodes):
                        loc = electrodes["location"][peak_channel]
                        if loc is not None and str(loc) != "nan":
                            area = str(loc)
                            area_status = "electrode_location"
                
                # 3. Check electrode_group description
                if area == "unresolved" and "electrode_group" in unit_cols:
                    eg = units_table["electrode_group"][unit_idx]
                    desc = getattr(eg, "description", None)
                    if desc:
                        area = str(desc)
                        area_status = "electrode_group_description"
                
                row["area"] = area
                row["area_status"] = area_status
                
                row["source_status"] = "ok" if area_status != "unresolved" else "unresolved_metadata"
                row["warnings"] = json.dumps(warns) if warns else ""
                
                rows.append(row)
            
        finally:
            if io is not None:
                io.close()
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    
    # Assign global unit IDs deterministically
    sort_cols = ["nwb_file", "probe_id", "peak_channel_global", "unit_id_in_nwb"]
    # Handle mixed types in sort
    for col in sort_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)
    df = df.sort_values(by=sort_cols).reset_index(drop=True)
    df["general_unit_id"] = np.arange(1, len(df) + 1)
    
    # Reorder columns to match spec
    spec_order = [
        "general_unit_id",
        "subject_id",
        "session_id",
        "nwb_file",
        "nwb_file_name",
        "nwb_size_bytes",
        "unit_id_in_nwb",
        "unit_row_index",
        "probe_id",
        "electrode_group",
        "area",
        "area_status",
        "peak_channel",
        "peak_channel_local",
        "peak_channel_global",
        "peak_channel_status",
        "n_spikes_total",
        "session_start_time_s",
        "session_stop_time_s",
        "session_duration_s",
        "bin_width_ms",
        "bin_width_s",
        "n_rate_bins",
        "min_firing_rate_hz",
        "max_firing_rate_hz",
        "mean_firing_rate_hz",
        "median_firing_rate_hz",
        "presence_ratio",
        "source_status",
        "warnings",
    ]
    
    # Only include columns that exist
    final_cols = [c for c in spec_order if c in df.columns]
    df = df[final_cols]
    
    # Write CSV if requested
    if out_csv:
        out_path = Path(out_csv)
        if not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not out_path.exists():
            df.to_csv(out_path, index=False)
    
    return df


# ============================================================================
# Function 2: LFP/Probe/Session Address Book
# ============================================================================

def build_lfp_session_address_book(
    nwb_paths: Iterable[str | Path],
    out_csv: str | Path | None = None,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Build LFP/probe/session address book from NWB files.
    
    Returns DataFrame with one row per probe or probe-area segment.
    """
    path_list = [Path(p) for p in nwb_paths]
    rows: list[dict] = []
    
    for nwb_path in path_list:
        nwbfile, io, warns = _open_nwb(nwb_path)
        
        try:
            session_id = getattr(nwbfile, "session_id", nwb_path.stem)
            subject_id = getattr(nwbfile, "subject", None)
            if subject_id is not None:
                subject_id = getattr(subject_id, "subject_id", str(subject_id))
            else:
                parts = nwb_path.stem.split("_")
                subject_id = parts[0] if parts else "unknown"
            
            nwb_size = nwb_path.stat().st_size
            
            # Get electrodes table
            electrodes = getattr(nwbfile, "electrodes", None)
            if electrodes is None:
                warns.append(_warn("NO_ELECTRODES", f"No electrodes in {nwb_path.name}"))
                continue
            
            n_electrodes = len(electrodes)
            electrode_cols = list(electrodes.colnames)
            
            # Get device/electrode groups
            elec_groups = defaultdict(list)
            for i in range(n_electrodes):
                if "group" in electrode_cols:
                    group = electrodes["group"][i]
                    group_name = getattr(group, "name", str(group))
                else:
                    group_name = "default"
                elec_groups[group_name].append(i)
            
            # Process each electrode group as a probe
            for group_name, indices in elec_groups.items():
                # Try to extract probe_id
                import re
                probe_match = re.search(r'probe[\s_]*(\d+)', group_name, re.IGNORECASE)
                if probe_match:
                    probe_id = int(probe_match.group(1))
                    probe_label = f"probe{probe_id}"
                else:
                    probe_id = group_name
                    probe_label = group_name
                
                # Get area string from group description or location
                area_string_raw = ""
                area_list = []
                area_status = "unresolved"
                
                if "group" in electrode_cols and indices:
                    group = electrodes["group"][indices[0]]
                    desc = getattr(group, "description", "")
                    if desc:
                        area_string_raw = str(desc)
                        # Parse area list from description
                        if "," in desc or ";" in desc or "/" in desc:
                            delim = "," if "," in desc else (";" if ";" in desc else "/")
                            area_list = [a.strip() for a in desc.split(delim)]
                        else:
                            area_list = [desc.strip()]
                        area_status = "electrode_group_description"
                
                # If no description, try location from first electrode
                if not area_list and "location" in electrode_cols and indices:
                    loc = electrodes["location"][indices[0]]
                    if loc:
                        area_string_raw = str(loc)
                        area_list = [area_string_raw]
                        area_status = "electrode_location"
                
                # Channel range
                channel_start_global = min(indices)
                channel_stop_global = max(indices) + 1  # exclusive
                n_channels = len(indices)
                
                # Get sampling rate from LFP if available
                sampling_rate_hz = None
                lfp_series_path = ""
                muae_series_path = ""
                
                acquisition = getattr(nwbfile, "acquisition", {})
                for name, obj in acquisition.items():
                    if "lfp" in name.lower() and hasattr(obj, "rate"):
                        if obj.rate is not None:
                            sampling_rate_hz = float(obj.rate)
                            lfp_series_path = f"acquisition/{name}"
                            break
                
                # Split channels into areas if multiple areas
                if len(area_list) > 1 and n_channels > 0:
                    # Divide channels into contiguous chunks
                    n_areas = len(area_list)
                    chunk_size = n_channels // n_areas
                    remainder = n_channels % n_areas
                    
                    start_local = 0
                    for i, area in enumerate(area_list):
                        # Distribute remainder across first chunks
                        this_chunk = chunk_size + (1 if i < remainder else 0)
                        end_local = start_local + this_chunk
                        
                        # Global indices
                        global_start = channel_start_global + start_local
                        global_end = channel_start_global + end_local
                        
                        row = {
                            "general_lfp_id": len(rows) + 1,
                            "subject_id": subject_id,
                            "session_id": session_id,
                            "nwb_file": str(nwb_path),
                            "nwb_file_name": nwb_path.name,
                            "nwb_size_bytes": nwb_size,
                            "probe_id": probe_id,
                            "probe_label": probe_label,
                            "electrode_group": group_name,
                            "device_name": "",
                            "area_string_raw": area_string_raw,
                            "area_list": ";".join(area_list),
                            "area_status": area_status,
                            "channel_index_start_global": global_start,
                            "channel_index_stop_global_exclusive": global_end,
                            "channel_index_range_global": f"{global_start}-{global_end - 1}",
                            "channel_index_start_local": start_local,
                            "channel_index_stop_local_exclusive": end_local,
                            "channel_index_range_local": f"{start_local}-{end_local - 1}",
                            "n_channels": this_chunk,
                            "sampling_rate_hz": sampling_rate_hz,
                            "lfp_series_path": lfp_series_path,
                            "muae_series_path": muae_series_path,
                            "source_status": "ok" if area_status != "unresolved" else "unresolved_metadata",
                            "warnings": json.dumps(warns) if warns else "",
                        }
                        rows.append(row)
                        start_local = end_local
                else:
                    # Single area or no area split
                    area = area_list[0] if area_list else "unresolved"
                    
                    row = {
                        "general_lfp_id": len(rows) + 1,
                        "subject_id": subject_id,
                        "session_id": session_id,
                        "nwb_file": str(nwb_path),
                        "nwb_file_name": nwb_path.name,
                        "nwb_size_bytes": nwb_size,
                        "probe_id": probe_id,
                        "probe_label": probe_label,
                        "electrode_group": group_name,
                        "device_name": "",
                        "area_string_raw": area_string_raw,
                        "area_list": ";".join(area_list) if area_list else "",
                        "area_status": area_status,
                        "channel_index_start_global": channel_start_global,
                        "channel_index_stop_global_exclusive": channel_stop_global,
                        "channel_index_range_global": f"{channel_start_global}-{channel_stop_global - 1}",
                        "channel_index_start_local": 0,
                        "channel_index_stop_local_exclusive": n_channels,
                        "channel_index_range_local": f"0-{n_channels - 1}" if n_channels > 0 else "",
                        "n_channels": n_channels,
                        "sampling_rate_hz": sampling_rate_hz,
                        "lfp_series_path": lfp_series_path,
                        "muae_series_path": muae_series_path,
                        "source_status": "ok" if area_status != "unresolved" else "unresolved_metadata",
                        "warnings": json.dumps(warns) if warns else "",
                    }
                    rows.append(row)
            
        finally:
            if io is not None:
                io.close()
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    
    # Spec column order
    spec_order = [
        "general_lfp_id",
        "subject_id",
        "session_id",
        "nwb_file",
        "nwb_file_name",
        "nwb_size_bytes",
        "probe_id",
        "probe_label",
        "electrode_group",
        "device_name",
        "area_string_raw",
        "area_list",
        "area_status",
        "channel_index_start_global",
        "channel_index_stop_global_exclusive",
        "channel_index_range_global",
        "channel_index_start_local",
        "channel_index_stop_local_exclusive",
        "channel_index_range_local",
        "n_channels",
        "sampling_rate_hz",
        "lfp_series_path",
        "muae_series_path",
        "source_status",
        "warnings",
    ]
    final_cols = [c for c in spec_order if c in df.columns]
    df = df[final_cols]
    
    if out_csv:
        out_path = Path(out_csv)
        if not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not out_path.exists():
            df.to_csv(out_path, index=False)
    
    return df


# ============================================================================
# Function 3: Event Timing Vectors
# ============================================================================

def get_event_timing_vectors(
    nwb_path: str | Path,
    event: Literal["p1", "flash"] = "p1",
    conditions: Sequence[str] | None = None,
) -> dict[str, np.ndarray]:
    """Get event timing vectors by condition from NWB.
    
    Returns dict mapping condition code to ndarray of event times (seconds).
    
    This function does NOT write files by default. Use save helpers for persistence.
    
    Typed blockers:
    - BLOCKED_EVENTS_TABLE_MISSING
    - BLOCKED_CONDITION_LABELS_MISSING
    - BLOCKED_P1_ONSETS_MISSING
    - BLOCKED_FLASH_ONSETS_MISSING
    - BLOCKED_UNSUPPORTED_EVENT_SCHEMA
    """
    path = Path(nwb_path)
    target_conditions = list(conditions) if conditions else CANONICAL_CONDITIONS
    
    nwbfile, io, warns = _open_nwb(path)
    
    try:
        intervals = getattr(nwbfile, "intervals", None)
        if intervals is None:
            raise RuntimeError("BLOCKED_EVENTS_TABLE_MISSING: No intervals table in NWB")
        
        # Look for omission_glo_passive or similar trial table
        trial_table_name = None
        for name in intervals.keys():
            if "omission" in name.lower() or "trial" in name.lower():
                trial_table_name = name
                break
        
        if trial_table_name is None:
            raise RuntimeError("BLOCKED_EVENTS_TABLE_MISSING: No omission/trial interval table found")
        
        table = intervals[trial_table_name]
        table_cols = list(table.colnames)
        
        # Check for condition column
        cond_col = None
        for col in ["task_condition_number", "condition", "trial_type", "condition_number"]:
            if col in table_cols:
                cond_col = col
                break
        
        if cond_col is None:
            raise RuntimeError("BLOCKED_CONDITION_LABELS_MISSING: No condition column found")
        
        # Check for event onset column
        onset_col = None
        if event == "p1":
            for col in ["start_time", "p1_onset", "stim1_onset", "onset"]:
                if col in table_cols:
                    onset_col = col
                    break
        elif event == "flash":
            for col in ["flash_onset", "start_time", "stim_onset"]:
                if col in table_cols:
                    onset_col = col
                    break
        
        if onset_col is None:
            if event == "p1":
                raise RuntimeError("BLOCKED_P1_ONSETS_MISSING: No P1 onset column found")
            else:
                raise RuntimeError("BLOCKED_FLASH_ONSETS_MISSING: No flash onset column found")
        
        # Load data
        condition_numbers = table[cond_col][:]
        onsets = table[onset_col][:]
        
        # Build result as dict of lists first, then convert to ndarrays
        result_lists: dict[str, list[float]] = {cond: [] for cond in target_conditions}
        
        # Map condition numbers to codes
        for i, cond_num in enumerate(condition_numbers):
            code = NUMBER_TO_CONDITION.get(int(float(cond_num)))
            if code and code in result_lists:
                result_lists[code].append(float(onsets[i]))
        
        # Check for missing conditions
        missing = [c for c in target_conditions if not result_lists[c]]
        if missing:
            warns.append(_warn("MISSING_CONDITIONS", f"No trials for conditions: {missing}"))
        
        # Convert to ndarrays for efficient runtime use
        result: dict[str, np.ndarray] = {
            cond: np.array(times, dtype=np.float64)
            for cond, times in result_lists.items()
        }
        
        return result
        
    finally:
        if io is not None:
            io.close()


def save_event_timing_vectors_npz(
    event_vectors: dict[str, np.ndarray],
    out_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save event timing vectors to NPZ format (efficient binary storage).
    
    Each condition gets its own array in the NPZ archive.
    Metadata is embedded as a JSON-serialized string under key 'metadata_json'.
    
    Preferred path format:
        outputs/data_index/event_timing_vectors_<subject>_<session>.npz
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build save dict: one array per condition
    save_dict: dict[str, np.ndarray] = {}
    
    # Store each condition vector
    for cond, times in event_vectors.items():
        # Sanitize key for NPZ (replace non-alphanumeric with underscore)
        safe_key = "".join(c if c.isalnum() else "_" for c in cond)
        save_dict[safe_key] = times
    
    # Build and store metadata
    meta = dict(metadata) if metadata else {}
    
    # Auto-compute counts_by_condition if not provided
    if "counts_by_condition" not in meta:
        meta["counts_by_condition"] = {
            cond: len(times) for cond, times in event_vectors.items()
        }
    
    # Add standard fields
    meta["conditions"] = list(event_vectors.keys())
    meta["time_unit"] = meta.get("time_unit", "seconds")
    meta["time_base"] = meta.get("time_base", "NWB")
    meta["saved_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    save_dict["metadata_json"] = np.array(json.dumps(meta, indent=2), dtype=np.str_)
    
    np.savez_compressed(out_path, **save_dict)


def load_event_timing_vectors_npz(
    path: str | Path,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Load event timing vectors from NPZ format.
    
    Returns:
        (event_vectors_dict, metadata_dict)
    
    Condition keys are restored to their original form.
    """
    path = Path(path)
    
    with np.load(path, allow_pickle=False) as data:
        # Extract metadata
        metadata_json = str(data["metadata_json"])
        metadata = json.loads(metadata_json)
        
        # Extract event vectors (skip metadata_json key)
        event_vectors: dict[str, np.ndarray] = {}
        for key in data.files:
            if key == "metadata_json":
                continue
            # Restore original condition key from metadata if available
            original_key = key
            if "conditions" in metadata:
                for cond in metadata["conditions"]:
                    safe_cond = "".join(c if c.isalnum() else "_" for c in cond)
                    if safe_cond == key:
                        original_key = cond
                        break
            event_vectors[original_key] = data[key]
        
        return event_vectors, metadata


def save_event_timing_vectors_json(
    event_vectors: dict[str, np.ndarray],
    out_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save event timing vectors to JSON (human-readable, for debugging/provenance).
    
    This is for inspection and debugging only - use NPZ for normal storage.
    
    Preferred path format:
        outputs/data_index/event_timing_vectors_<subject>_<session>.json
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    payload: dict[str, Any] = {
        "time_unit": "seconds",
        "time_base": "NWB",
        "conditions": list(event_vectors.keys()),
        "counts_by_condition": {
            cond: len(times) for cond, times in event_vectors.items()
        },
        "event_vectors": {
            cond: times.tolist() for cond, times in event_vectors.items()
        },
        "metadata": dict(metadata) if metadata else {},
        "saved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def export_event_timing_vectors_csv(
    event_vectors: dict[str, np.ndarray],
    out_path: str | Path,
) -> None:
    """Export event timing vectors to CSV long-table format (for interoperability only).
    
    This is OPTIONAL and should not be used by downstream analysis code.
    Use NPZ for normal storage - this is only for external tool compatibility.
    
    CSV format:
        condition,event,onset_s,trial_index
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    rows: list[dict[str, Any]] = []
    for cond, times in event_vectors.items():
        for trial_idx, onset_s in enumerate(times):
            rows.append({
                "condition": cond,
                "event": "p1",  # Default, can be parameterized if needed
                "onset_s": float(onset_s),
                "trial_index": trial_idx,
            })
    
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)


# ============================================================================
# Function 4: Channel Area/Layer Map
# ============================================================================

def estimate_channel_area_layer_map(
    nwb_path: str | Path,
    probe_id: str | int | None = None,
    infer_layers: bool = False,
    layer_window_channels: int = 40,
) -> pd.DataFrame:
    """Estimate channel-to-area/layer mapping from NWB.
    
    Returns DataFrame with one row per channel.
    """
    path = Path(nwb_path)
    nwbfile, io, warns = _open_nwb(path)
    
    try:
        session_id = getattr(nwbfile, "session_id", path.stem)
        subject_id = getattr(nwbfile, "subject", None)
        if subject_id is not None:
            subject_id = getattr(subject_id, "subject_id", str(subject_id))
        else:
            parts = path.stem.split("_")
            subject_id = parts[0] if parts else "unknown"
        
        electrodes = getattr(nwbfile, "electrodes", None)
        if electrodes is None:
            raise RuntimeError("BLOCKED_NO_ELECTRODES: No electrodes table")
        
        n_electrodes = len(electrodes)
        electrode_cols = list(electrodes.colnames)
        
        rows: list[dict] = []
        
        for ch_idx in range(n_electrodes):
            row: dict[str, Any] = {
                "subject_id": subject_id,
                "session_id": session_id,
                "nwb_file": str(path),
                "channel_index_global": ch_idx,
                "electrode_id": ch_idx,
            }
            
            # Get electrode group (probe)
            if "group" in electrode_cols:
                group = electrodes["group"][ch_idx]
                group_name = getattr(group, "name", str(group))
                row["electrode_group"] = group_name
                
                # Extract probe label
                import re
                probe_match = re.search(r'probe[\s_]*(\d+)', group_name, re.IGNORECASE)
                if probe_match:
                    row["probe_id"] = int(probe_match.group(1))
                    row["probe_label"] = f"probe{probe_match.group(1)}"
                else:
                    row["probe_id"] = group_name
                    row["probe_label"] = group_name
            else:
                row["electrode_group"] = "default"
                row["probe_id"] = 0
                row["probe_label"] = "probe0"
            
            # Filter by probe_id if specified
            if probe_id is not None:
                if str(row["probe_id"]) != str(probe_id):
                    continue
            
            # Compute local channel index within probe
            # Need to count channels in same group before this one
            local_idx = 0
            for i in range(ch_idx):
                if "group" in electrode_cols:
                    other_group = electrodes["group"][i]
                    other_name = getattr(other_group, "name", str(other_group))
                    if other_name == row["electrode_group"]:
                        local_idx += 1
            row["channel_index_local"] = local_idx
            
            # Get area
            area = "unresolved"
            area_status = "unresolved"
            area_string_raw = ""
            
            if "location" in electrode_cols:
                loc = electrodes["location"][ch_idx]
                if loc is not None and str(loc) != "nan":
                    area = str(loc)
                    area_status = "electrode_location"
                    area_string_raw = area
            
            if area == "unresolved" and "group" in electrode_cols:
                group = electrodes["group"][ch_idx]
                desc = getattr(group, "description", None)
                if desc:
                    area_string_raw = str(desc)
                    # Parse multi-area
                    if "," in area_string_raw or ";" in area_string_raw or "/" in area_string_raw:
                        delim = "," if "," in area_string_raw else (";" if ";" in area_string_raw else "/")
                        areas = [a.strip() for a in area_string_raw.split(delim)]
                        # Assign based on local channel position
                        # This requires knowing total channels in group
                        # Simplified: just use the first area
                        area = areas[0] if areas else area_string_raw
                        area_status = "electrode_group_description_parsed"
                    else:
                        area = area_string_raw
                        area_status = "electrode_group_description"
            
            row["area"] = area
            row["area_status"] = area_status
            row["area_string_raw"] = area_string_raw
            
            # Layer (default: unresolved)
            row["layer"] = "unresolved"
            row["layer_status"] = "unresolved"
            row["layer_inference_method"] = "not_computed"
            
            if infer_layers:
                # Placeholder for layer inference
                # Would require LFP analysis - not implemented in minimal version
                row["layer_status"] = "not_computed"
                row["layer_inference_method"] = "not_implemented_in_minimal"
            
            # Power bands (placeholder for optional layer inference)
            row["gamma_power"] = None
            row["alpha_beta_power"] = None
            row["gamma_alpha_beta_ratio"] = None
            
            row["source_status"] = "ok" if area_status != "unresolved" else "unresolved_metadata"
            row["warnings"] = json.dumps(warns) if warns else ""
            
            rows.append(row)
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # Spec column order
        spec_order = [
            "subject_id",
            "session_id",
            "nwb_file",
            "probe_id",
            "probe_label",
            "electrode_group",
            "channel_index_global",
            "channel_index_local",
            "electrode_id",
            "area",
            "area_status",
            "area_string_raw",
            "layer",
            "layer_status",
            "layer_inference_method",
            "gamma_power",
            "alpha_beta_power",
            "gamma_alpha_beta_ratio",
            "source_status",
            "warnings",
        ]
        final_cols = [c for c in spec_order if c in df.columns]
        df = df[final_cols]
        
        return df
        
    finally:
        if io is not None:
            io.close()


# ============================================================================
# Function 5: Aligned Unit Signal Extraction
# ============================================================================

def get_aligned_unit_signals(
    nwb_path: str | Path,
    unit_filter: Mapping[str, object],
    event_vectors: Mapping[str, Sequence[float]],
    pre_ms: float,
    post_ms: float,
    bin_ms: float | None = None,
) -> Mapping[str, object]:
    """Extract trial-aligned spike data for selected units.
    
    Returns dict with aligned spike data.
    
    If bin_ms is None: returns ragged relative spike times.
    If bin_ms is set: returns dense binned array (trial x unit x time_bin).
    """
    path = Path(nwb_path)
    nwbfile, io, warns = _open_nwb(path)
    
    try:
        units_table = getattr(nwbfile, "units", None)
        if units_table is None:
            raise RuntimeError("BLOCKED_NO_UNITS: No units table in NWB")
        
        n_units = len(units_table)
        unit_cols = list(units_table.colnames)
        
        # Apply filter to select units
        selected_indices = []
        selected_metadata = []
        
        for unit_idx in range(n_units):
            # Check filter criteria
            include = True
            
            # Area filter
            if "area" in unit_filter:
                target_area = unit_filter["area"]
                # Get unit area (simplified - would use unit address book lookup)
                unit_area = "unresolved"
                if "area" in unit_cols:
                    val = units_table["area"][unit_idx]
                    if val is not None:
                        unit_area = str(val)
                if unit_area != target_area:
                    include = False
            
            # Presence ratio filter
            if "presence_ratio_min" in unit_filter and include:
                min_pr = unit_filter["presence_ratio_min"]
                # Would compute - for now, skip
                pass
            
            if include:
                selected_indices.append(unit_idx)
                # Get unit ID
                if "unit_id" in unit_cols:
                    uid = str(units_table["unit_id"][unit_idx])
                else:
                    uid = f"unit_{unit_idx}"
                selected_metadata.append({"unit_idx": unit_idx, "unit_id": uid})
        
        if not selected_indices:
            warns.append(_warn("NO_UNITS_SELECTED", f"No units matched filter: {unit_filter}"))
        
        # Prepare time axis
        time_axis_ms = np.arange(pre_ms, post_ms + (bin_ms or 1.0), (bin_ms or 1.0))
        
        result = {
            "signal_class": "SPK",
            "time_unit": "ms",
            "event_time_unit": "seconds",
            "pre_ms": pre_ms,
            "post_ms": post_ms,
            "bin_ms": bin_ms,
            "time_axis_ms": time_axis_ms,
            "conditions": list(event_vectors.keys()),
            "n_units_selected": len(selected_indices),
            "n_units_total": n_units,
            "unit_table": pd.DataFrame(selected_metadata),
            "spikes": {},
            "spike_times_relative": {},
            "provenance": {
                "nwb_path": str(path),
                "unit_filter": dict(unit_filter),
                "n_events_per_condition": {k: len(v) for k, v in event_vectors.items()},
            },
            "warnings": warns,
        }
        
        # Process each condition
        for condition, event_times_sec in event_vectors.items():
            event_times_ms = [t * 1000.0 for t in event_times_sec]  # Convert to ms
            n_trials = len(event_times_ms)
            n_sel = len(selected_indices)
            
            if bin_ms is not None:
                # Dense binned output
                bin_edges = np.arange(pre_ms, post_ms + bin_ms, bin_ms)
                n_bins = len(bin_edges) - 1
                
                # Initialize array: trial x unit x time_bin
                binned = np.zeros((n_trials, n_sel, n_bins), dtype=np.int32)
                
                for trial_idx, event_ms in enumerate(event_times_ms):
                    for sel_idx, unit_idx in enumerate(selected_indices):
                        spike_times = units_table["spike_times"][unit_idx]
                        if hasattr(spike_times, "data"):
                            spike_times = np.asarray(spike_times.data[:])
                        else:
                            spike_times = np.asarray(spike_times)
                        
                        # Align to event
                        aligned_ms = (spike_times * 1000.0) - event_ms
                        
                        # Filter to window
                        in_window = (aligned_ms >= pre_ms) & (aligned_ms < post_ms)
                        window_spikes = aligned_ms[in_window]
                        
                        # Bin
                        if len(window_spikes) > 0:
                            counts, _ = np.histogram(window_spikes, bins=bin_edges)
                            binned[trial_idx, sel_idx, :] = counts
                
                result["spikes"][condition] = binned
            else:
                # Ragged output
                trial_spikes = []
                for trial_idx, event_ms in enumerate(event_times_ms):
                    unit_spikes = []
                    for unit_idx in selected_indices:
                        spike_times = units_table["spike_times"][unit_idx]
                        if hasattr(spike_times, "data"):
                            spike_times = np.asarray(spike_times.data[:])
                        else:
                            spike_times = np.asarray(spike_times)
                        
                        aligned_ms = (spike_times * 1000.0) - event_ms
                        in_window = (aligned_ms >= pre_ms) & (aligned_ms < post_ms)
                        window_spikes = aligned_ms[in_window].tolist()
                        unit_spikes.append(window_spikes)
                    trial_spikes.append(unit_spikes)
                
                result["spike_times_relative"][condition] = trial_spikes
        
        return result
        
    finally:
        if io is not None:
            io.close()
