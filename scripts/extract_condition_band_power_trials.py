r"""
Per-trial band-power time series, per session x area x band x condition (RXRR, RRRR) --
the input jnwb.connectivity.granger() needs for a directed LFP-LFP connectivity network
(fig05, 2026-08-04 redesign).

WHY THIS EXISTS
    Every existing TFR dataset in this repo (extract_condition_tfr_maps.py,
    extract_omission_tfr_maps.py, extract_stimulus_pooled_tfr_maps.py) pools trials before
    storage -- sums/counts per session|area|... key, no per-trial axis survives. granger(X, Y)
    needs (n_trials, n_times) per node and fits its AR model with rows stacked over trials
    (never crossing a trial boundary, see jnwb/connectivity.py's _stack_var_design), so this is
    a genuinely new data product, not a reshape of an existing one.

MEASURE (same estimator discipline as extract_condition_tfr_maps.py, applied per trial)
    Baseline b(ch, f) = mean power over the middle third of d1 (706-856 ms from p1),
    averaged over ALL trials and the baseline window -- one stable per-channel reference,
    not each trial's own (noisier) baseline window. Every trial's power at every time bin is
    then divided by that fixed per-channel baseline: ratio(trial, ch, f, t) = power / b(ch, f).
    Per trial: average the ratio across a band's frequency rows, then across the channels
    within an area (average ratio, never average decibels), THEN take 10*log10 once at the
    very end -- same "average in ratio space, log last" rule as every other extraction here.

TIME BASE / CONDITIONS -- identical to extract_condition_tfr_maps.py
    -500 to +2593 ms from p1 onset (fx-p1-d1-p2-d2-p3), 10 ms bins, RXRR (p2 omitted) and
    RRRR (p2 real), p1-aligned for both so no per-condition slot offset is needed.

OUTPUT
    outputs/condition_band_power_trials/trials.npz   one (n_trials, n_times) float32 array per
        "session|area|cond|band" key (ragged across keys -- trial counts differ by session and
        condition, which is why this is many independently-shaped arrays, not one stacked one)
    outputs/condition_band_power_trials/index.csv
    outputs/condition_band_power_trials/receipt.json
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
from jnwb import paths as _P

TFR_DIR = _P.tfr_dir()
AREA_VEC = _P.REPO_ROOT / "outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/condition_band_power_trials"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES_SRC = 500
T0_SRC_MS, BIN_MS = -1000.0, 10.0

WIN_MS = (-500, 2593)                                # p1 onset to the p3/d3 boundary
N_TIMES = int(round((WIN_MS[1] - WIN_MS[0]) / BIN_MS))
TIMES = WIN_MS[0] + np.arange(N_TIMES) * BIN_MS
BASELINE_MS = (706, 856)                             # middle third of d1, see module docstring

CONDS = ["RXRR", "RRRR"]
BANDS = {"theta": (4, 8), "alpha": (8, 14), "beta": (14, 30),
         "low_gamma": (30, 50), "high_gamma": (50, 80)}
BAND_SEL = {name: (FREQS_HZ >= lo) & (FREQS_HZ < hi) for name, (lo, hi) in BANDS.items()}
AREA_POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
CHUNK = 16

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    av = pd.read_csv(AREA_VEC)
    seg = {}
    for (sp, pl, a), g in av.groupby(["session_prefix", "probe_letter", "area"]):
        seg[(sp, pl, a)] = g.sort_values("channel")["channel"].to_numpy()

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
        targets.append((f, g, seg[key]))
    if limit:
        targets = targets[:limit]
    print(f"[{datetime.now():%H:%M:%S}] {len(targets)} files", flush=True)

    i0 = int(round((WIN_MS[0] - T0_SRC_MS) / BIN_MS))
    i1 = i0 + N_TIMES
    b0 = int(round((BASELINE_MS[0] - T0_SRC_MS) / BIN_MS)) - i0
    b1 = int(round((BASELINE_MS[1] - T0_SRC_MS) / BIN_MS)) - i0

    # acc_sum/acc_cnt[session|area|cond][band] -> (n_trials, N_TIMES) running sum/count over
    # channels contributed by (possibly several) files for that area. Ragged across sessions x
    # conditions by trial count, never across bands/times within one key.
    acc_sum = {}
    acc_cnt = {}
    n_trials_seen = {}
    meta = defaultdict(lambda: {"n_channels": 0})
    t_start = time.time()
    n_ragged_trials = 0

    for k, (f, g, chans) in enumerate(targets, 1):
        try:
            arr = np.load(f, mmap_mode="r")
        except Exception as e:
            skipped.append((os.path.basename(f), f"load failed: {e}"))
            continue
        if arr.ndim != 4 or arr.shape[2] != len(FREQS_HZ) or arr.shape[3] != N_TIMES_SRC:
            skipped.append((os.path.basename(f), f"shape {arr.shape}"))
            continue

        area10 = AREA_POOL.get(g["area"], g["area"])
        cond = g["cond"]
        session = g["session_prefix"]
        key = f"{session}|{area10}|{cond}"
        n_tr = arr.shape[0]
        if key in n_trials_seen and n_trials_seen[key] != n_tr:
            n_tr = min(n_trials_seen[key], n_tr)
            n_ragged_trials += 1
        n_trials_seen[key] = n_tr

        sel = chans[chans < arr.shape[1]]
        for c0 in range(0, sel.size, CHUNK):
            ch_block = sel[c0:c0 + CHUNK]
            buf = np.asarray(arr[:n_tr, ch_block, :, i0:i1], dtype=np.float32)  # (tr,ch,f,t)
            with np.errstate(divide="ignore", invalid="ignore"):
                b_bar = np.nanmean(buf[:, :, :, b0:b1], axis=(0, 3))            # (ch,f)
                ratio = buf / b_bar[None, :, :, None]                          # (tr,ch,f,t)
            ratio[~np.isfinite(ratio)] = np.nan
            ratio[ratio <= 0] = np.nan

            if key not in acc_sum:
                acc_sum[key] = {b: np.zeros((n_tr, N_TIMES), dtype=np.float64) for b in BANDS}
                acc_cnt[key] = {b: np.zeros((n_tr, N_TIMES), dtype=np.float64) for b in BANDS}
            elif acc_sum[key]["theta"].shape[0] != n_tr:
                # a later file for this key reports fewer trials than the running accumulator
                # was sized for -- truncate the accumulator down rather than lose the file.
                for b in BANDS:
                    acc_sum[key][b] = acc_sum[key][b][:n_tr]
                    acc_cnt[key][b] = acc_cnt[key][b][:n_tr]

            for band, fsel in BAND_SEL.items():
                band_ratio = np.nanmean(ratio[:, :, fsel, :], axis=2)          # (tr,ch,t)
                good = np.isfinite(band_ratio)
                s = np.where(good, band_ratio, 0.0).sum(axis=1)                # (tr,t)
                c = good.sum(axis=1).astype(np.float64)                        # (tr,t)
                acc_sum[key][band] += s
                acc_cnt[key][band] += c
            meta[key]["n_channels"] += len(ch_block)

        if k % 50 == 0:
            print(f"[{datetime.now():%H:%M:%S}]  {k}/{len(targets)}, {len(acc_sum)} keys, "
                  f"{time.time()-t_start:.0f}s", flush=True)

    out_arrays = {}
    rows = []
    for key in sorted(acc_sum):
        for band in BANDS:
            s, c = acc_sum[key][band], acc_cnt[key][band]
            with np.errstate(invalid="ignore", divide="ignore"):
                ratio_mean = np.where(c > 0, s / np.maximum(c, 1), np.nan)
                db = 10.0 * np.log10(ratio_mean)
            out_arrays[f"{key}|{band}"] = db.astype(np.float32)
        session, area, cond = key.split("|")
        rows.append({"key": key, "session": session, "area": area, "cond": cond,
                     "n_trials": acc_sum[key]["theta"].shape[0],
                     "n_channels": meta[key]["n_channels"]})

    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez_compressed(os.path.join(OUT_DIR, "trials.npz"), times=TIMES, **out_arrays)
    idx = pd.DataFrame(rows)
    idx.to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Per-trial band-power dB time series per session x area x cond x band, for "
                  "granger()-based directed LFP-LFP connectivity (fig05, 2026-08-04 redesign).",
        "source_dir": TFR_DIR, "area_vector": AREA_VEC,
        "n_files_processed": len(targets), "n_files_skipped": len(skipped),
        "skipped": skipped[:50], "conditions": CONDS, "bands_hz": BANDS,
        "n_ragged_trial_count_files": n_ragged_trials,
        "window_ms_re_p1": list(WIN_MS), "n_time_bins": N_TIMES, "bin_ms": BIN_MS,
        "baseline_ms_re_p1": list(BASELINE_MS),
        "baseline_scope": "per channel, mean over ALL trials and the middle-of-d1 window -- "
                          "one stable per-channel reference applied to every individual trial, "
                          "not each trial's own baseline window",
        "estimator_order": "ratio per trial per channel -> mean ratio across the band's "
                           "frequency rows -> mean ratio across channels within the area -> "
                           "10*log10 once, at the very end",
        "stored_quantity": "dB power change from baseline, per trial, per (session, area, "
                           "cond, band) key -- ragged n_trials across keys",
        "area_pooling": AREA_POOL,
        "n_keys": len(acc_sum), "areas": sorted(idx.area.unique().tolist()),
        "runtime_s": round(time.time() - t_start, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/trials.npz ({len(acc_sum)} keys x {len(BANDS)} bands), "
         f"index.csv, receipt.json")
    print(f"areas={sorted(idx.area.unique().tolist())}  runtime={receipt['runtime_s']}s")


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
