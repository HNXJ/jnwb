r"""
Time-resolved RXRR/RRXR-vs-RRRR time-frequency maps, per session x area x putative layer.
(RRXR added 2026-07-31 for a per-subject V182o band-trace supplement -- p3-omission alongside
the original p2-omission RXRR comparison; same extraction, same baseline, just one more
condition value pulled from files that already existed on disk.)

WHY THIS EXISTS
    Every other TFR map in this repo (extract_omission_tfr_maps.py) pools all nine omission
    conditions together and aligns to the omitted slot. RRRR -- the no-omission R-family
    control -- has no omitted slot and is excluded from that pooling entirely. Comparing what
    happens at position 2 under omission (RXRR) against what happens there when a real
    stimulus is shown (RRRR) needs both conditions kept separate and aligned to the same
    trial-relative clock (p1 onset), not to an event that only one of them has.

MEASURE
    For every channel, every trial, every frequency:
        dB(f, t) = 10 * log10( power(f, t) / baseline(f) )
        baseline(f) = mean power over the MIDDLE of d1, not a pre-trial fixation window.
    d1 (531-1031 ms) is the delay after the first real stimulus and before the object of
    comparison (p2, real in RRRR / omitted in RXRR); its middle third is late enough that any
    p1-evoked transient has decayed and early enough that it cannot anticipate p2. Each
    channel is referenced to its OWN baseline; no channel is normalised by another channel,
    area or session.

TIME BASE
    -500 to +2593 ms from p1 onset, 10 ms bins -- covers fx-p1-d1-p2-d2-p3 exactly (p3 ends at
    the p3->d3 boundary, 2593 ms). Alignment is p1 onset for BOTH conditions; unlike the
    omission-pooled extraction there is no per-file slot offset and no late-trial truncation
    to track, because neither RXRR (omission fixed at position 2) nor RRRR (no omission) can
    run out of trial before +2593 ms.

OUTPUT
    outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz   sums and counts, keyed session|area|layer|cond
    outputs/condition_tfr_maps_p1d1p2d2p3/index.csv
    outputs/condition_tfr_maps_p1d1p2d2p3/receipt.json
"""
from __future__ import annotations

import glob
import json
import os
import platform
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

TFR_DIR = r"D:/workspace/data/tfr_arrays"
AREA_VEC = r"D:/workspace/omission/outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = r"D:/workspace/omission/outputs/condition_tfr_maps_p1d1p2d2p3"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES_SRC = 500
T0_SRC_MS, BIN_MS = -1000.0, 10.0

WIN_MS = (-500, 2593)                                # p1 onset to the p3/d3 boundary
N_TIMES = int(round((WIN_MS[1] - WIN_MS[0]) / BIN_MS))
TIMES = WIN_MS[0] + np.arange(N_TIMES) * BIN_MS
# The middle third of d1 (531-1031 ms), not a pre-trial baseline -- see module docstring.
BASELINE_MS = (706, 856)

CONDS = ["RXRR", "RRXR", "RRRR"]
AREA_POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
CHUNK = 16

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    av = pd.read_csv(AREA_VEC)
    seg, lay = {}, {}
    for (sp, pl, a), g in av.groupby(["session_prefix", "probe_letter", "area"]):
        g = g.sort_values("channel")
        seg[(sp, pl, a)] = g["channel"].to_numpy()
        lay[(sp, pl, a)] = dict(zip(g["channel"],
                                    g.get("putative_layer", pd.Series(index=g.index))))

    targets, skipped = [], []
    for f in sorted(glob.glob(os.path.join(TFR_DIR, "*.npy"))):
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if not m:
            continue
        g = m.groupdict()
        if g["cond"] not in CONDS:
            continue
        g["session_prefix"] = f"sub-{g['subject']}_ses-{g['session']}"
        key = (g["session_prefix"], g["probe"], g["area"])
        if key not in seg:
            skipped.append((os.path.basename(f), "no channel segment"))
            continue
        targets.append((f, g, seg[key], lay.get(key, {})))
    if limit:
        targets = targets[:limit]
    print(f"[{datetime.now():%H:%M:%S}] {len(targets)} files", flush=True)

    i0 = int(round((WIN_MS[0] - T0_SRC_MS) / BIN_MS))
    i1 = i0 + N_TIMES
    b0 = int(round((BASELINE_MS[0] - T0_SRC_MS) / BIN_MS)) - i0
    b1 = int(round((BASELINE_MS[1] - T0_SRC_MS) / BIN_MS)) - i0

    acc_sum = defaultdict(lambda: np.zeros((len(FREQS_HZ), N_TIMES)))
    acc_cnt = defaultdict(lambda: np.zeros((len(FREQS_HZ), N_TIMES)))
    meta = defaultdict(lambda: {"n_channels": 0, "n_trials": 0})
    t_start = time.time()

    for k, (f, g, chans, lmap) in enumerate(targets, 1):
        try:
            arr = np.load(f, mmap_mode="r")
        except Exception as e:
            skipped.append((os.path.basename(f), f"load failed: {e}"))
            continue
        if arr.ndim != 4 or arr.shape[2] != len(FREQS_HZ) or arr.shape[3] != N_TIMES_SRC:
            skipped.append((os.path.basename(f), f"shape {arr.shape}"))
            continue
        if i0 < 0 or i1 > N_TIMES_SRC:
            skipped.append((os.path.basename(f), "window outside source time axis"))
            continue

        sel = chans[chans < arr.shape[1]]
        area10 = AREA_POOL.get(g["area"], g["area"])
        cond = g["cond"]

        for c0 in range(0, sel.size, CHUNK):
            ch_block = sel[c0:c0 + CHUNK]
            buf = np.asarray(arr[:, ch_block, :, i0:i1], dtype=np.float32)   # (trials,nch,f,t)
            # Same estimator as extract_omission_tfr_maps.py: trial-mean power first, THEN the
            # ratio, THEN the logarithm once at the very end (never average decibels).
            with np.errstate(divide="ignore", invalid="ignore"):
                p_bar = np.nanmean(buf, axis=0)                              # (nch, f, t)
                b_bar = np.nanmean(buf[:, :, :, b0:b1], axis=(0, 3))         # (nch, f)
                dbv = p_bar / b_bar[:, :, None]
            dbv[~np.isfinite(dbv)] = np.nan
            dbv[dbv <= 0] = np.nan
            dbv = dbv[None, ...]

            for j, ch in enumerate(ch_block):
                layer = lmap.get(int(ch), None)
                layer = "unknown" if (layer is None or (isinstance(layer, float)
                                                        and np.isnan(layer))) else str(layer)
                block = dbv[:, j]
                good = np.isfinite(block)
                s = np.where(good, block, 0.0).sum(axis=0).astype(np.float64)
                c = good.sum(axis=0).astype(np.float64)
                for key in (f"{g['session_prefix']}|{area10}|all|{cond}",
                           f"{g['session_prefix']}|{area10}|{layer}|{cond}"):
                    acc_sum[key] += s
                    acc_cnt[key] += c
                    meta[key]["n_trials"] += int(buf.shape[0])
                meta[f"{g['session_prefix']}|{area10}|all|{cond}"]["n_channels"] += 1
                meta[f"{g['session_prefix']}|{area10}|{layer}|{cond}"]["n_channels"] += 1

        if k % 50 == 0:
            print(f"[{datetime.now():%H:%M:%S}]  {k}/{len(targets)}, {len(acc_sum)} keys, "
                  f"{time.time()-t_start:.0f}s", flush=True)

    keys = sorted(acc_sum)
    np.savez_compressed(
        os.path.join(OUT_DIR, "maps.npz"),
        keys=np.array(keys),
        sums=np.stack([acc_sum[k] for k in keys]).astype(np.float32),
        counts=np.stack([acc_cnt[k] for k in keys]).astype(np.float32),
        freqs=FREQS_HZ, times=TIMES)

    idx = pd.DataFrame([{
        "key": k, "session_prefix": k.split("|")[0], "area": k.split("|")[1],
        "layer": k.split("|")[2], "cond": k.split("|")[3],
        "n_channels": meta[k]["n_channels"], "n_channel_trials": meta[k]["n_trials"],
    } for k in keys])
    idx.to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "RXRR/RRXR-vs-RRRR dB maps per session x area x putative layer, p1-aligned, "
                   "each channel referenced to its own middle-of-d1 baseline.",
        "source_dir": TFR_DIR, "area_vector": AREA_VEC,
        "n_files_processed": len(targets), "n_files_skipped": len(skipped),
        "skipped": skipped[:50], "conditions": CONDS,
        "window_ms_re_p1": list(WIN_MS), "n_time_bins": N_TIMES, "bin_ms": BIN_MS,
        "baseline_ms_re_p1": list(BASELINE_MS),
        "baseline_scope": "per channel, per trial, per frequency; the MIDDLE THIRD of d1, not "
                          "a pre-trial fixation window -- see module docstring",
        "stored_quantity": "POWER RATIO power(f,t)/baseline(f), NOT decibels. Sums and counts "
                           "are of the ratio; take 10*log10 once, after all averaging.",
        "alignment": "p1 onset (t=0) for both conditions; no per-file slot offset and no "
                     "late-trial truncation, unlike the omission-pooled extraction",
        "freqs_hz": [int(FREQS_HZ[0]), int(FREQS_HZ[-1]), 2],
        "area_pooling": AREA_POOL,
        "areas": sorted(idx.area.unique().tolist()),
        "layers": sorted(idx.layer.unique().tolist()),
        "n_keys": len(keys),
        "runtime_s": round(time.time() - t_start, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/maps.npz ({len(keys)} keys), index.csv, receipt.json")
    print(f"areas={receipt['areas']}  runtime={receipt['runtime_s']}s")


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
