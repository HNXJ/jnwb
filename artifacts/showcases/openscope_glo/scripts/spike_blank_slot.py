"""Blank-slot test of the spike clock against the stimulus table (one session).

Usage: python scripts/spike_blank_slot.py SESSION_ID OUT_JSON

Population PSTH (every 10th spike of all units, 20-ms bins) around P1 onsets of blocks 3-39,
from 5 slots before to 5 after (slot = 1.001 s; P1-P4 then a blank). Per slot: the peak of the
PSTH over its median and the peak's latency. A response in each stimulus slot and none in the
blank slots means the spike and stimulus clocks agree to well under one slot.
"""
import json
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from glo_common import assets, receipt  # noqa: E402

SLOT = 1.001


def main():
    ses, out = sys.argv[1], sys.argv[2]
    with h5py.File(Path(assets()[ses]["dest"]), "r") as f:
        g = f["intervals/init_grating_presentations"]
        st, ori, blk = g["start_time"][()], g["orientation"][()], g["stimulus_block"][()]
        sp = np.sort(f["units/spike_times"][()][::10])
    p1 = st[np.isfinite(ori) & np.r_[True, ~np.isfinite(ori[:-1])] & np.isin(blk, list(range(3, 40)))]
    edges = np.arange(-5.0, 5.0001, 0.02)
    h = np.zeros(len(edges) - 1)
    for t in p1:
        lo, hi = np.searchsorted(sp, [t - 5, t + 5])
        h += np.histogram(sp[lo:hi] - t, edges)[0]
    c, h = edges[:-1] + 0.01, h / np.median(h)
    slots = {}
    for k in range(-5, 5):
        w = (c >= k * SLOT) & (c < (k + 1) * SLOT)
        i = int(np.argmax(h[w]))
        slots[str(k)] = {"kind": "blank" if k in (-1, 4) else f"P{(k % 5) + 1}", "peak_over_median": float(h[w][i]),
                         "peak_ms": float((c[w][i] - k * SLOT) * 1e3)}
    print({k: (v["kind"], round(v["peak_over_median"], 2), round(v["peak_ms"])) for k, v in slots.items()})
    json.dump(receipt({"session": ses, "n_p1": int(len(p1)), "slots": slots}), open(out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
