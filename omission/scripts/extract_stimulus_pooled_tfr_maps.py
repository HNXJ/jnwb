r"""
Time-resolved stimulus-aligned time-frequency maps, per session x area x putative layer --
the matched counterpart to extract_omission_tfr_maps.py's omission-pooled dataset.

WHY THIS EXISTS
    extract_omission_tfr_maps.py pools all nine omission conditions (AAAX/AAXB/AXAB/BBBX/
    BBXA/BXBA/RRRX/RRXR/RXRR), aligned to the omitted slot, into one omission-pooled dB map
    per session x area x layer. There was no matched STIMULUS-pooled counterpart: a fair
    comparison needs the same pooling breadth on the "something was really there" side, not
    just p2 of the no-omission control (which is all fig04's p1-aligned RRRR/AAAB/BBBA
    comparison gives). 2026-08-04, built on request to support a slot-aligned omission-vs-
    stimulus supplement.

MEASURE (identical convention to extract_omission_tfr_maps.py)
    For every channel, every trial, every frequency:
        dB(f, t) = 10 * log10( power(f, t) / baseline(f) )
        baseline(f) = mean power over -250 to -50 ms relative to the ALIGNED stimulus onset
    Each channel referenced to its own pre-stimulus baseline; ratio of expected power (trial-
    mean power first, then divide by baseline, log once at the very end -- never average
    decibels, see extract_omission_tfr_maps.py's own note on the measured -0.17 to -1.98 dB
    bias this order avoids).

ALIGNMENT
    STIM_CONDS = AAAB, BBBA, RRRR -- the three families' no-early-omission control
    conditions, which have a REAL stimulus at every one of the four slots. Each is read once
    per slot in STIM_SLOTS = (2, 3, 4) -- the same three positions the omission side's nine
    conditions cover (X at position 2, 3, or 4) -- and every (condition, slot) pair is pooled
    into the SAME accumulator per session x area x layer, exactly as the omission side pools
    its nine (condition, implied-slot) pairs. 3 conditions x 3 slots = 9 pseudo-conditions,
    matching the omission side's 9 exactly in count and slot-position distribution, so the two
    pooled datasets are a like-for-like comparison, not just similarly-shaped ones.

    p1 (slot 1) is deliberately excluded, matching the omission side (no condition omits p1 --
    GLO_CONDITIONS never puts X in position 1).

TIME BASE
    -1500 to +1500 ms relative to the aligned stimulus onset, 200 bins of 10 ms -- identical
    window to extract_omission_tfr_maps.py. Slot-4 alignments run out of source samples before
    +1500 ms (source arrays end at +3990 ms from p1, slot 4 onset is at +3093 ms); those bins
    accumulate as missing, not zero-filled, same truncation handling as the omission side.

OUTPUT
    outputs/stimulus_pooled_tfr_maps_w1500/maps.npz   sums and counts, keyed session|area|layer
    outputs/stimulus_pooled_tfr_maps_w1500/index.csv
    outputs/stimulus_pooled_tfr_maps_w1500/receipt.json
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
OUT_DIR = _P.REPO_ROOT / "outputs/stimulus_pooled_tfr_maps_w1500"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES_SRC = 500
T0_SRC_MS, BIN_MS = -1000.0, 10.0

EPOCH_ONSET_MS = {"fx": -500, "p1": 0, "d1": 531, "p2": 1031, "d2": 1562,
                  "p3": 2062, "d3": 2593, "p4": 3093, "d4": 3624}

WIN_MS = (-1500, 1500)                     # relative to the aligned stimulus onset
N_TIMES = int((WIN_MS[1] - WIN_MS[0]) / BIN_MS)      # 200
TIMES_STIM = WIN_MS[0] + np.arange(N_TIMES) * BIN_MS
BASELINE_REL_MS = (-250, -50)

STIM_CONDS = ["AAAB", "BBBA", "RRRR"]
STIM_SLOTS = (2, 3, 4)                      # matches the omission side's 9 (cond, slot) pairs
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
        if g["cond"] not in STIM_CONDS:
            continue
        g["session_prefix"] = f"sub-{g['subject']}_ses-{g['session']}"
        key = (g["session_prefix"], g["probe"], g["area"])
        if key not in seg:
            skipped.append((os.path.basename(f), "no channel segment"))
            continue
        targets.append((f, g, seg[key], lay.get(key, {})))
    if limit:
        targets = targets[:limit]
    # Each file is read once but contributes to all len(STIM_SLOTS) alignments -- 3x the
    # per-file work of the omission extraction, which reads each file for a single slot.
    print(f"[{datetime.now():%H:%M:%S}] {len(targets)} files x {len(STIM_SLOTS)} slots",
          flush=True)

    acc_sum = defaultdict(lambda: np.zeros((len(FREQS_HZ), N_TIMES)))
    acc_cnt = defaultdict(lambda: np.zeros((len(FREQS_HZ), N_TIMES)))
    meta = defaultdict(lambda: {"n_channels": 0, "n_trials": 0, "conds": set()})
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

        sel = chans[chans < arr.shape[1]]
        area10 = AREA_POOL.get(g["area"], g["area"])

        for slot in STIM_SLOTS:
            p_on = EPOCH_ONSET_MS[f"p{slot}"]
            i0 = int(round((p_on + WIN_MS[0] - T0_SRC_MS) / BIN_MS))
            i1 = i0 + N_TIMES
            s0, s1 = max(0, i0), min(N_TIMES_SRC, i1)
            d0, d1 = s0 - i0, s0 - i0 + (s1 - s0)
            if s1 <= s0:
                skipped.append((os.path.basename(f), f"slot {slot} window outside source axis"))
                continue
            b0 = int(round((BASELINE_REL_MS[0] - WIN_MS[0]) / BIN_MS))
            b1 = int(round((BASELINE_REL_MS[1] - WIN_MS[0]) / BIN_MS))
            pseudo_cond = f"{g['cond']}_p{slot}"

            for c0 in range(0, sel.size, CHUNK):
                ch_block = sel[c0:c0 + CHUNK]
                raw = np.asarray(arr[:, ch_block, :, s0:s1], dtype=np.float32)
                buf = np.full((raw.shape[0], raw.shape[1], len(FREQS_HZ), N_TIMES),
                              np.nan, dtype=np.float32)
                buf[:, :, :, d0:d1] = raw
                # Same estimator as extract_omission_tfr_maps.py: trial-mean power first,
                # THEN the ratio, THEN the logarithm once at the very end.
                with np.errstate(divide="ignore", invalid="ignore"):
                    p_bar = np.nanmean(buf, axis=0)
                    b_bar = np.nanmean(buf[:, :, :, b0:b1], axis=(0, 3))
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
                    for key in (f"{g['session_prefix']}|{area10}|all",
                               f"{g['session_prefix']}|{area10}|{layer}"):
                        acc_sum[key] += s
                        acc_cnt[key] += c
                        meta[key]["n_trials"] += int(np.isfinite(buf[:, j, 0, 0]).sum())
                        meta[key]["conds"].add(pseudo_cond)
                    meta[f"{g['session_prefix']}|{area10}|all"]["n_channels"] += 1
                    meta[f"{g['session_prefix']}|{area10}|{layer}"]["n_channels"] += 1

        if k % 50 == 0:
            print(f"[{datetime.now():%H:%M:%S}]  {k}/{len(targets)}, {len(acc_sum)} keys, "
                  f"{time.time()-t_start:.0f}s", flush=True)

    keys = sorted(acc_sum)
    np.savez_compressed(
        os.path.join(OUT_DIR, "maps.npz"),
        keys=np.array(keys),
        sums=np.stack([acc_sum[k] for k in keys]).astype(np.float32),
        counts=np.stack([acc_cnt[k] for k in keys]).astype(np.float32),
        freqs=FREQS_HZ, times=TIMES_STIM)

    idx = pd.DataFrame([{
        "key": k, "session_prefix": k.split("|")[0], "area": k.split("|")[1],
        "layer": k.split("|")[2], "n_channels": meta[k]["n_channels"],
        "n_channel_trials": meta[k]["n_trials"],
        "n_pseudo_conditions": len(meta[k]["conds"]),
    } for k in keys])
    idx.to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Time-resolved stimulus-aligned dB maps per session x area x putative "
                  "layer -- the matched counterpart to extract_omission_tfr_maps.py's "
                  "omission-pooled dataset, each channel referenced to its own pre-stimulus "
                  "baseline.",
        "source_dir": TFR_DIR, "area_vector": AREA_VEC,
        "stim_conds": STIM_CONDS, "stim_slots": list(STIM_SLOTS),
        "n_pseudo_conditions_pooled": len(STIM_CONDS) * len(STIM_SLOTS),
        "n_files_processed": len(targets), "n_files_skipped": len(skipped),
        "skipped": skipped[:50],
        "window_ms_re_stimulus": list(WIN_MS), "n_time_bins": N_TIMES, "bin_ms": BIN_MS,
        "baseline_ms_re_stimulus": list(BASELINE_REL_MS),
        "baseline_scope": "per channel, per trial, per frequency; no cross-area or "
                          "cross-session normalisation anywhere",
        "stored_quantity": "POWER RATIO power(f,t)/baseline(f), NOT decibels. Sums and counts "
                           "are of the ratio; take 10*log10 once, after all averaging.",
        "freqs_hz": [int(FREQS_HZ[0]), int(FREQS_HZ[-1]), 2],
        "area_pooling": AREA_POOL,
        "areas": sorted(idx.area.unique().tolist()),
        "layers": sorted(idx.layer.unique().tolist()),
        "n_keys": len(keys),
        "slot4_truncation": "the p4 alignment runs out of source samples ~100 ms before "
                            "+1500 ms (source arrays end at +3990 ms from p1, slot 4 onset is "
                            "+3093 ms); those bins accumulate as missing, not zero-filled, "
                            "same handling as extract_omission_tfr_maps.py's late-slot case.",
        "runtime_s": round(time.time() - t_start, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/maps.npz ({len(keys)} keys), index.csv, receipt.json")
    print(f"areas={receipt['areas']}\nlayers={receipt['layers']}  runtime={receipt['runtime_s']}s")


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
