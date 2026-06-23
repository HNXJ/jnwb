#!/usr/bin/env python3
"""
Find units whose firing rate during fixation (fx) or after delay d4
exceeds three times their overall average firing rate.

Outputs a CSV with columns:
session_id, unit_id, avg_firing_rate_hz, fx_rate_hz, d4_rate_hz, peak_type

peak_type can be 'fx', 'd4', or 'fx & d4'.
"""
import argparse
import csv
from pathlib import Path
import numpy as np
import pandas as pd

# Timing windows (ms) based on task spec
FX_START_MS = 500
FX_END_MS = 1000
D4_START_MS = 3624
D4_END_MS = 4124

def load_grand_db(csv_path: Path):
    df = pd.read_csv(csv_path)
    mapping = {}
    for _, row in df.iterrows():
        key = (int(row['session_id']), int(row['unit_id']))
        mapping[key] = float(row['firing_rate'])
    return mapping

def locate_spk_file(data_root: Path, filename: str) -> Path:
    for p in data_root.rglob(filename):
        return p
    raise FileNotFoundError(f"Spk file {filename} not found under {data_root}")

def compute_rate(unit_spk: np.ndarray, start_ms: int, end_ms: int) -> float:
    # unit_spk shape: (trials, timepoints)
    window = unit_spk[:, start_ms:end_ms]
    # Mean spikes per ms across trials, then convert to Hz
    mean_spikes_per_ms = window.mean()
    return float(mean_spikes_per_ms * 1000.0)

def process_spk_file(spk_path: Path, session_id: int, avg_rate_map: dict, results: list):
    arr = np.load(spk_path, mmap_mode='r')
    n_trials, n_units, n_time = arr.shape
    for unit_idx in range(n_units):
        key = (session_id, unit_idx)
        avg_rate = avg_rate_map.get(key)
        if avg_rate is None:
            continue
        unit_spk = arr[:, unit_idx, :]
        fx_rate = compute_rate(unit_spk, FX_START_MS, FX_END_MS)
        d4_rate = compute_rate(unit_spk, D4_START_MS, D4_END_MS)
        peak = []
        if fx_rate >= 3 * avg_rate:
            peak.append('fx')
        if d4_rate >= 3 * avg_rate:
            peak.append('d4')
        if peak:
            results.append({
                'session_id': session_id,
                'unit_id': unit_idx,
                'avg_firing_rate_hz': avg_rate,
                'fx_rate_hz': fx_rate,
                'd4_rate_hz': d4_rate,
                'peak_type': ' & '.join(peak)
            })

def main():
    parser = argparse.ArgumentParser(description='Identify fixation/d4 peak firing units')
    parser.add_argument('--data-root', required=True, help='Root directory containing spk .npy files')
    parser.add_argument('--grand-csv', required=True, help='Path to grand_database_6040_units.csv')
    parser.add_argument('--a7-inventory', required=True, help='Path to spk_smoke_file_inventory.csv')
    parser.add_argument('--out-csv', required=True, help='Output CSV path')
    args = parser.parse_args()

    data_root = Path(args.data_root)
    avg_rate_map = load_grand_db(Path(args.grand_csv))

    results = []
    with open(args.a7_inventory, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['time_axis_status'] != 'valid_timebase_6000ms':
                continue
            session_id = int(row['session_id'])
            source_file = row['source_file']
            spk_path = locate_spk_file(data_root, source_file)
            process_spk_file(spk_path, session_id, avg_rate_map, results)

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ['session_id', 'unit_id', 'avg_firing_rate_hz', 'fx_rate_hz', 'd4_rate_hz', 'peak_type']
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

if __name__ == '__main__':
    main()
