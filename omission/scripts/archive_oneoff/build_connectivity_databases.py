"""
scripts/build_connectivity_databases.py

Processes all NWB sessions and generates two databases for functional connectivity:
1. Complex TFR HDF5 database:
   Path: D:/workspace/data/connectivity_databases/{session_prefix}_complex_tfr.h5
   Dimensions: (n_channels, n_bands, n_conditions, n_events, n_trials) complex64
2. Spiking rate HDF5 database:
   Path: D:/workspace/data/connectivity_databases/{session_prefix}_spiking_rate.h5
   Dimensions: (n_units, n_conditions, n_events, n_trials) float32
3. Units Metadata CSV:
   Path: D:/workspace/data/connectivity_databases/{session_prefix}_units_metadata.csv

Supports 12 conditions, 5 bands, and 18 events (first and second half of fx, p1-p4, d1-d4).
Uses scipy.signal.spectrogram in mode='complex' on NWB raw LFP data to get actual phase and amplitude.
"""

from __future__ import annotations

import argparse
import sys
import os
import json
import warnings
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import signal

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

NWB_DIR = Path("D:/analysis/nwb")
DB_DIR = Path("D:/workspace/data/connectivity_databases")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"

# 12 standard condition groups
CONDITIONS = ["AAAB", "AAAX", "AAXB", "AXAB", "BBBA", "BBBX", "BBXA", "BXBA", "RRRR", "RRRX", "RRXR", "RXRR"]

# 5 standard frequency bands
BANDS = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 12.0),
    "beta": (12.0, 30.0),
    "low_gamma": (30.0, 55.0),
    "high_gamma": (55.0, 90.0)
}
BAND_NAMES = list(BANDS.keys())

# Define the 18 event half-intervals relative to trial onset (p1 = 0)
EPOCH_BOUNDS_MS = {
    "fx_1": (-500.0, -250.0),
    "fx_2": (-250.0, 0.0),
    "p1_1": (0.0, 265.5),
    "p1_2": (265.5, 531.0),
    "d1_1": (531.0, 781.0),
    "d1_2": (781.0, 1031.0),
    "p2_1": (1031.0, 1296.5),
    "p2_2": (1296.5, 1562.0),
    "d2_1": (1562.0, 1812.0),
    "d2_2": (1812.0, 2062.0),
    "p3_1": (2062.0, 2327.5),
    "p3_2": (2327.5, 2593.0),
    "d3_1": (2593.0, 2843.0),
    "d3_2": (2843.0, 3093.0),
    "p4_1": (3093.0, 3358.5),
    "p4_2": (3358.5, 3624.0),
    "d4_1": (3624.0, 3874.0),
    "d4_2": (3874.0, 4124.0),
}
EVENT_NAMES = list(EPOCH_BOUNDS_MS.keys())


def load_raw_lfp_datasets(f: h5py.File) -> list[tuple[str, h5py.Dataset, float]]:
    """Locate raw LFP dataset(s) and sampling rates in NWB."""
    datasets = []
    # Check acquisition/probe_{0..3}_lfp
    for pi in range(4):
        key = f"probe_{pi}_lfp"
        if f"acquisition/{key}/data" in f:
            data_ds = f[f"acquisition/{key}/data"]
            # Look for timestamps to get fs
            ts = f[f"acquisition/{key}/timestamps"][:] if f"acquisition/{key}/timestamps" in f else None
            fs = 1000.0 if ts is None or len(ts) < 2 else float(1.0 / np.median(np.diff(ts)))
            datasets.append((key, data_ds, fs))
        elif f"acquisition/{key}/{key}_data/data" in f:
            data_ds = f[f"acquisition/{key}/{key}_data/data"]
            ts = f[f"acquisition/{key}/{key}_data/timestamps"][:] if f"acquisition/{key}/{key}_data/timestamps" in f else None
            fs = 1000.0 if ts is None or len(ts) < 2 else float(1.0 / np.median(np.diff(ts)))
            datasets.append((key, data_ds, fs))
    return datasets


def process_session(nwb_path: Path) -> None:
    session_prefix = nwb_path.stem.replace("_rec", "")
    print(f"\n=======================================================")
    print(f"Processing session: {session_prefix}")
    print(f"=======================================================")

    # Read session metadata
    try:
        session = oa.read(str(nwb_path))
    except Exception as e:
        print(f"  [ERROR] Failed to load session via jnwb: {e}")
        return

    units_df = session.get_units()
    if len(units_df) == 0:
        print("  [WARN] No units found in session.")
        return

    # Load classification templates
    grand_class_path = REPO_ROOT / "outputs/classification/grand_template_classifications.csv"
    if grand_class_path.exists():
        grand_class = pd.read_csv(grand_class_path)
        sess_class = grand_class[grand_class["session_prefix"] == session_prefix]
    else:
        sess_class = pd.DataFrame()

    # Build units metadata CSV
    units_metadata = []
    for idx, row in units_df.iterrows():
        unit_id = row.get("unit_id", idx)
        peak_ch = row.get("peak_channel_global", row.get("peak_channel_id", np.nan))
        area = row.get("area", "unknown")
        layer = row.get("layer", "unknown")
        
        # Match template label
        label = "Null"
        if not sess_class.empty:
            match = sess_class[sess_class["unit_row_idx"] == idx]
            if not match.empty:
                label = match.iloc[0]["template_label"]

        units_metadata.append({
            "unit_row_idx": idx,
            "unit_id": unit_id,
            "peak_channel_id": peak_ch,
            "area": area,
            "putative_layer": layer,
            "template_label": label
        })
    df_meta = pd.DataFrame(units_metadata)
    meta_path = DB_DIR / f"{session_prefix}_units_metadata.csv"
    df_meta.to_csv(meta_path, index=False)
    print(f"  Wrote units metadata to {meta_path.name}")

    # Initialize spiking rate database
    spiking_db_path = DB_DIR / f"{session_prefix}_spiking_rate.h5"
    with h5py.File(spiking_db_path, "w") as sf:
        # Pre-extract spike times for all units
        all_spikes = []
        for idx in range(len(units_df)):
            st = session.get_spike_times(idx)
            all_spikes.append(st if st is not None else np.array([]))

        for cond in CONDITIONS:
            # Extract trial onset times
            epochs = session.get_epochs(phase=2, condition=cond, correct_only=True)
            if len(epochs) == 0:
                continue
            onsets = epochs["start_time"].values
            n_trials = len(onsets)

            # Dimensions: (n_units, n_events, n_trials)
            cond_rates = np.zeros((len(units_df), len(EVENT_NAMES), n_trials), dtype=np.float32)

            for ti, onset in enumerate(onsets):
                for ei, event_name in enumerate(EVENT_NAMES):
                    t0_ms, t1_ms = EPOCH_BOUNDS_MS[event_name]
                    t0 = onset + (t0_ms / 1000.0)
                    t1 = onset + (t1_ms / 1000.0)
                    duration = t1 - t0

                    for ui in range(len(units_df)):
                        spikes = all_spikes[ui]
                        # Count spikes in this sub-interval
                        count = np.sum((spikes >= t0) & (spikes < t1))
                        cond_rates[ui, ei, ti] = count / duration

            sf.create_dataset(cond, data=cond_rates, compression="gzip")
            print(f"    Spiking Rate: processed {cond} ({n_trials} trials)")

    print(f"  Wrote spiking rates to {spiking_db_path.name}")

    # Process LFP Complex Spectra
    lfp_db_path = DB_DIR / f"{session_prefix}_complex_tfr.h5"
    with h5py.File(nwb_path, "r") as f_nwb:
        lfp_datasets = load_raw_lfp_datasets(f_nwb)
        if not lfp_datasets:
            print("  [WARN] No raw LFP datasets found in NWB.")
            return

        # We assume 128 channels globally
        n_channels = 128
        with h5py.File(lfp_db_path, "w") as lf:
            # Loop condition groups
            for cond in CONDITIONS:
                epochs = session.get_epochs(phase=2, condition=cond, correct_only=True)
                if len(epochs) == 0:
                    continue
                onsets = epochs["start_time"].values
                n_trials = len(onsets)

                # Dims: (n_channels, n_bands, n_events, n_trials) complex64
                cond_complex = np.zeros((n_channels, len(BAND_NAMES), len(EVENT_NAMES), n_trials), dtype=np.complex64)

                # Extract segments across trial onsets
                # LFP is continuous in NWB. We extract [-1.0s, +4.5s] relative to trial onset to run spectrogram.
                # Segment window covers all events (-500ms to 4124ms)
                win_pre = 1.0  # seconds before onset
                win_post = 4.5  # seconds after onset

                # Process probe dataset(s)
                for key, data_ds, fs in lfp_datasets:
                    # We determine channel index mapping. Most probes cover 128 channels.
                    # Since NWB LFP is stored continuously, we load the trial segments.
                    n_ch_ds = data_ds.shape[1]
                    ch_limit = min(n_channels, n_ch_ds)

                    # Build trial segment data
                    for ti, onset in enumerate(onsets):
                        sample_start = int(round((onset - win_pre) * fs))
                        sample_stop = int(round((onset + win_post) * fs))

                        if sample_start < 0 or sample_stop > data_ds.shape[0]:
                            continue  # trial out of LFP bounds

                        # Load chunk: (n_samples, n_channels)
                        try:
                            seg = data_ds[sample_start:sample_stop, :ch_limit]
                        except Exception as e:
                            print(f"      [WARN] Failed to load LFP chunk: {e}")
                            continue

                        # Compute spectrogram in mode='complex'
                        # Hann window, 200ms duration, 10ms hop
                        nperseg = max(64, int(round(fs * 0.2)))
                        noverlap = nperseg - int(round(fs * 0.01))
                        noverlap = max(0, min(noverlap, nperseg - 1))

                        for ch in range(ch_limit):
                            freqs_sg, times_sg, Sxx = signal.spectrogram(
                                seg[:, ch],
                                fs=fs,
                                window="hann",
                                nperseg=nperseg,
                                noverlap=noverlap,
                                detrend=False,
                                scaling="spectrum",
                                mode="complex"
                            )

                            # Sxx is (n_freqs, n_times_sg) complex
                            # Shift times relative to trial onset (p1 = 0)
                            t_ms = (times_sg - win_pre) * 1000.0

                            # Map to bands and events
                            for bi, band_name in enumerate(BAND_NAMES):
                                f_lo, f_hi = BANDS[band_name]
                                f_mask = (freqs_sg >= f_lo) & (freqs_sg < f_hi)
                                if not f_mask.any():
                                    continue

                                # Mean complex coefficient across frequency band
                                band_tfr = Sxx[f_mask, :].mean(axis=0)  # (n_times_sg,)

                                for ei, event_name in enumerate(EVENT_NAMES):
                                    t0, t1 = EPOCH_BOUNDS_MS[event_name]
                                    t_mask = (t_ms >= t0) & (t_ms < t1)
                                    if t_mask.any():
                                        # Mean complex coefficient across the event interval
                                        cond_complex[ch, bi, ei, ti] = band_tfr[t_mask].mean()

                lf.create_dataset(cond, data=cond_complex, compression="gzip")
                print(f"    Complex LFP: processed {cond} ({n_trials} trials)")

    print(f"  Wrote complex TFR to {lfp_db_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build connectivity databases.")
    parser.add_argument("--session", default=None, help="Process a single session prefix.")
    args = parser.parse_args()

    DB_DIR.mkdir(parents=True, exist_ok=True)

    # Filter read sessions
    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    if args.session:
        ready = ready[ready["session_prefix"] == args.session]

    if len(ready) == 0:
        print("No matching ready sessions found.")
        return

    print(f"Found {len(ready)} ready sessions to process.")
    for _, row in ready.iterrows():
        nwb_file = NWB_DIR / (row["session_prefix"] + "_rec.nwb")
        if not nwb_file.exists():
            nwb_file = NWB_DIR / (row["session_prefix"] + ".nwb")
        if not nwb_file.exists():
            print(f"[WARN] NWB file not found for {row['session_prefix']}")
            continue
        process_session(nwb_file)

    print("\nConnectivity database generation finished successfully!")


if __name__ == "__main__":
    # Disable duplicate NWB construct logs
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
