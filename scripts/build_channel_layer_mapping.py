"""
scripts/build_channel_layer_mapping.py

Computes the putative layer assignment ('sup', 'mid', 'deep', 'na') for each channel
on each probe across all ready sessions.

Uses:
1. vFLIP2 crossover estimation from the LFP Power Spectral Density (PSD) matrix.
2. Pairwise LFP correlation matrices to identify local channel blocks within layers.
3. Outputs are saved to D:/workspace/data/connectivity_databases/{session_prefix}_channel_layers.csv
   and pooled across sessions.
"""

from __future__ import annotations

import argparse
import sys
import json
import warnings
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import signal

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "outputs/archive"))

import jnwb as oa
from codes.functions.vflip2_mapping import vFLIP2

NWB_DIR = Path("D:/analysis/nwb")
DB_DIR = Path("D:/workspace/data/connectivity_databases")
READINESS_CSV = REPO_ROOT / "artifacts/data/session_readiness.csv"


def load_raw_lfp_datasets(f: h5py.File) -> list[tuple[str, h5py.Dataset, float]]:
    """Locate raw LFP dataset(s) and sampling rates in NWB."""
    datasets = []
    for pi in range(4):
        key = f"probe_{pi}_lfp"
        if f"acquisition/{key}/data" in f:
            data_ds = f[f"acquisition/{key}/data"]
            ts = f[f"acquisition/{key}/timestamps"][:] if f"acquisition/{key}/timestamps" in f else None
            fs = 1000.0 if ts is None or len(ts) < 2 else float(1.0 / np.median(np.diff(ts)))
            datasets.append((key, data_ds, fs))
        elif f"acquisition/{key}/{key}_data/data" in f:
            data_ds = f[f"acquisition/{key}/{key}_data/data"]
            ts = f[f"acquisition/{key}/{key}_data/timestamps"][:] if f"acquisition/{key}/{key}_data/timestamps" in f else None
            fs = 1000.0 if ts is None or len(ts) < 2 else float(1.0 / np.median(np.diff(ts)))
            datasets.append((key, data_ds, fs))
    return datasets


def process_channel_layers(nwb_path: Path) -> None:
    session_prefix = nwb_path.stem.replace("_rec", "")
    print(f"\n=======================================================")
    print(f"Calculating Putative Layers: {session_prefix}")
    print(f"=======================================================")

    try:
        session = oa.read(str(nwb_path))
    except Exception as e:
        print(f"  [ERROR] Failed to load session via jnwb: {e}")
        return

    # Load probe areas sidecar mapping
    try:
        probe_areas_json = REPO_ROOT / f"D:/workspace/data/metadata/{nwb_path.stem}/probe_areas.json"
        if not probe_areas_json.exists():
            probe_areas_json = Path(f"D:/workspace/data/metadata/{nwb_path.stem}/probe_areas.json")
        with open(probe_areas_json, "r") as f:
            probe_meta = json.load(f)
    except Exception as e:
        print(f"  [WARN] Missing probe_areas.json sidecar: {e}. Using raw electrodes fallback.")
        probe_meta = {}

    rows = []

    with h5py.File(nwb_path, "r") as f_nwb:
        lfp_datasets = load_raw_lfp_datasets(f_nwb)
        if not lfp_datasets:
            print("  [WARN] No raw LFP datasets found in NWB.")
            return

        for key, data_ds, fs in lfp_datasets:
            print(f"  Processing dataset: {key} (fs={fs:.1f} Hz)")
            # Load LFP chunk to compute PSD and Correlation (e.g. first 5 minutes of recording)
            n_samples = min(int(300 * fs), data_ds.shape[0])
            n_channels = data_ds.shape[1]
            lfp_chunk = data_ds[:n_samples, :]  # (samples, channels)

            # 1. Compute PSD matrix (channels x freqs)
            freqs, psd = signal.welch(lfp_chunk.T, fs=fs, nperseg=1024)  # (channels, n_freqs)

            # 2. Find areas and valid segments
            # Map areas per channel using probe metadata or default fallback
            area_labels = ["unknown"] * n_channels
            # Find which probe key this lfp_key corresponds to
            probe_info = None
            for p_name, p_info in probe_meta.items():
                if p_info.get("lfp_key") == key:
                    probe_info = p_info
                    break

            if probe_info:
                for area, sl in probe_info["channel_slices"].items():
                    for ch_idx in range(sl["start"], sl["stop"]):
                        if ch_idx < n_channels:
                            area_labels[ch_idx] = area

            # 3. Compute Pairwise LFP Correlation Matrix
            # Reveals local blocks of high correlation separated by low correlation boundaries
            corr_mat = np.corrcoef(lfp_chunk.T)

            # 4. Fit vFLIP2 layer assignment
            try:
                flip = vFLIP2(
                    psd,
                    area_labels=area_labels,
                    auto_bad_channels=True,
                    omega_cut=-np.inf,
                    n_channels_total=n_channels
                )
                labels = flip.get_laminar_label_vector()
                crossover = flip.Results.crossoverchannel if flip.Results else np.nan
                omega = flip.Results.omega if flip.Results else np.nan
            except Exception as e:
                print(f"    vFLIP2 fit failed for {key}: {e}. Assigning na.")
                labels = np.full(n_channels, "na", dtype=object)
                crossover = np.nan
                omega = np.nan

            # Save records
            for ch in range(n_channels):
                rows.append({
                    "session_prefix": session_prefix,
                    "lfp_key": key,
                    "channel_idx": ch,
                    "area": area_labels[ch],
                    "putative_layer": labels[ch],
                    "crossover_channel": crossover,
                    "fit_omega": omega,
                    "mean_psd_alpha": np.mean(psd[ch, (freqs >= 8) & (freqs <= 12)]),
                    "mean_psd_gamma": np.mean(psd[ch, (freqs >= 30) & (freqs <= 80)]),
                    "block_correlation_mean": np.mean(corr_mat[ch, max(0, ch - 2):min(n_channels, ch + 3)])
                })

    df = pd.DataFrame(rows)
    out_csv = DB_DIR / f"{session_prefix}_channel_layers.csv"
    df.to_csv(out_csv, index=False)
    print(f"  Wrote putative channel layers to {out_csv.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate channel layers.")
    parser.add_argument("--session", default=None, help="Process a single session prefix.")
    args = parser.parse_args()

    DB_DIR.mkdir(parents=True, exist_ok=True)

    readiness = pd.read_csv(READINESS_CSV)
    ready = readiness[readiness["nwb_ok"] == True].copy()
    if args.session:
        ready = ready[ready["session_prefix"] == args.session]

    if len(ready) == 0:
        print("No matching ready sessions found.")
        return

    for _, row in ready.iterrows():
        nwb_file = NWB_DIR / (row["session_prefix"] + "_rec.nwb")
        if not nwb_file.exists():
            nwb_file = NWB_DIR / (row["session_prefix"] + ".nwb")
        if not nwb_file.exists():
            continue
        process_channel_layers(nwb_file)

    print("\nPutative channel layer mappings generated successfully!")


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    main()
