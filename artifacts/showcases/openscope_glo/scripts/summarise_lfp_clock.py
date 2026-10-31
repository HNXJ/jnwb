"""Table of the spike-triggered LFP clock offsets in receipts/lfp_clock_sta_*.json.

Usage: python scripts/summarise_lfp_clock.py
Prints one row per session, probe and file version: time axis, median offset (stored LFP time
minus spike time, ms) and the range across units in the early and late windows, units used.
"""
import json
from pathlib import Path

REC = Path(__file__).resolve().parents[1] / "receipts"
for f in sorted(REC.glob("lfp_clock_sta_*_probe-*.json")):
    r = json.load(open(f))
    for v, d in r["versions"].items():
        if "same_asset_as" in d:
            print(f"| {r['session']} | {r['probe']} | {v} | same asset as {d['same_asset_as']} | | | |")
            continue
        e, l = d["windows"]["early"], d["windows"]["late"]
        drift = l["median_offset_ms"] - e["median_offset_ms"]
        print(f"| {r['session']} | {r['probe']} | {v} | {d['time_axis']} | {e['median_offset_ms']:.2f} "
              f"[{e['range_offset_ms'][0]:.2f}, {e['range_offset_ms'][1]:.2f}] ({e['n_units_trough_z_below_-8']}) | "
              f"{l['median_offset_ms']:.2f} [{l['range_offset_ms'][0]:.2f}, {l['range_offset_ms'][1]:.2f}] "
              f"({l['n_units_trough_z_below_-8']}) | {drift:+.2f} |")
