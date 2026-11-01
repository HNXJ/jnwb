"""Blank-slot test of an LFP time axis against the stimulus table (session 1232959154, local file).

Usage: python scripts/lfp_clock_blank_slot.py OUT_JSON

The grating stream steps every 1.001 s and leaves every fifth slot blank (P1-P4, blank). The
evoked LFP averaged over P1 onsets of blocks 3-11, from 5 slots before to 5 after, must show a
response in each stimulus slot and none in the blank slots when the axis is right. Tested axes:
the paper-version timestamps / 30 kHz as stored, and the same plus 3.5768 s (the spike-triggered
estimate in receipts/lfp_clock_sta_1232959154_probe-1.json). Channel local index 274 (VISpm4).
Per slot: the peak-to-peak range of the mean, and its largest deviation in the first 400 ms.
"""
import json
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from glo_common import DATA, assets, receipt  # noqa: E402

FS, SLOT = 1250.0, 1.001


def main():
    ogen = Path(assets()["1232959154"]["dest"])
    with h5py.File(ogen, "r") as f:
        g = f["intervals/init_grating_presentations"]
        st, ori, blk = g["start_time"][()], g["orientation"][()], g["stimulus_block"][()]
    p1 = st[np.isfinite(ori) & np.r_[True, ~np.isfinite(ori[:-1])] & np.isin(blk, list(range(3, 12)))]
    rec = {"n_p1": int(len(p1)), "channel_local_index": 274, "axes": {}}
    with h5py.File(DATA / "sub-649323_ses-1232959154_probe-1_ecephys.nwb", "r") as f:
        s = f["acquisition/probe_1_lfp/probe_1_lfp_data"]
        t_old = s["timestamps"][()] / 30000.0
        c = int(np.flatnonzero(f["general/extracellular_ephys/electrodes/local_index"][()] == 274)[0])
        n = int(5 * SLOT * FS)
        for name, shift in (("ticks_over_30k", 0.0), ("ticks_over_30k_plus_3.5768", 3.5768)):
            ax = t_old + shift
            segs = [s["data"][i - n:i + n, c] for i in np.searchsorted(ax, p1)]
            m = np.asarray(segs, float).mean(0) * 1e6
            lag = np.arange(len(m)) / FS - 5 * SLOT
            slots = {}
            for k in range(-5, 5):
                w = (lag >= k * SLOT) & (lag < (k + 1) * SLOT)
                mm = m[w] - m[w][: int(0.04 * FS)].mean()
                i = int(np.argmax(np.abs(mm[: int(0.4 * FS)])))
                slots[str(k)] = {"kind": "blank" if k in (-1, 4) else f"P{(k % 5) + 1}",
                                 "range_uV": float(mm.max() - mm.min()), "extreme_uV": float(mm[i]), "extreme_ms": float(i / FS * 1e3)}
            rec["axes"][name] = slots
            print(name, {k: (v["kind"], round(v["range_uV"])) for k, v in slots.items()})
    json.dump(receipt(rec), open(sys.argv[1], "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
