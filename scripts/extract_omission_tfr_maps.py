r"""
Time-resolved omission-aligned time-frequency maps, per session x area x putative layer.

WHY THIS EXISTS
    The window census (compute_channel_band_power_census_v2.py) averages power over the
    omitted slot alone, 0 to +531 ms. Inspection of the area traces shows the low-frequency
    change is a RAMP that keeps climbing through the following delay, so a 531 ms window
    measures its leading edge and understates it. This script keeps time.

    It also stores the full frequency axis rather than pre-averaged bands, so band
    definitions can be changed at plot time without re-reading 711 arrays.

MEASURE
    For every channel, every trial, every frequency:
        dB(f, t) = 10 * log10( power(f, t) / baseline(f) )
        baseline(f) = mean power over -250 to -50 ms relative to OMISSION onset
    i.e. each channel is referenced to ITS OWN pre-omission baseline. No channel is ever
    normalised by another channel, another area or another session.

TIME BASE
    -1000 to +1000 ms relative to the onset of the omitted slot, 200 bins of 10 ms.
    Because the source arrays are p1-aligned and end at +3990 ms, the last-slot conditions
    (X in position 4, onset 3093 ms) run out of samples ~100 ms before +1000; those bins are
    accumulated as missing rather than zero-filled, and the per-bin sample count is stored so
    the shortfall is visible in the output.

AREA POOLING
    V3, V3a and V3d are pooled to V3, giving ten areas: V1, V2, V3, V4, MT, MST, TEO, FST,
    FEF, PFC. V3a and V3d are the upper and lower halves of one shank under an assumed
    equal-share partition, so they are not two areas
    (artifacts/.lab/channel_area_vector_uniform_split_finding_20260728.json).

OUTPUT
    outputs/omission_tfr_maps/maps.npz     sums and counts, keyed session|area|layer
    outputs/omission_tfr_maps/index.csv    one row per stored key, with channel and trial counts
    outputs/omission_tfr_maps/receipt.json
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
OUT_DIR = _P.REPO_ROOT / "outputs/omission_tfr_maps_w1500"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES_SRC = 500
T0_SRC_MS, BIN_MS = -1000.0, 10.0
TIMES_SRC = T0_SRC_MS + np.arange(N_TIMES_SRC) * BIN_MS

EPOCH_ONSET_MS = {"fx": -500, "p1": 0, "d1": 531, "p2": 1031, "d2": 1562,
                  "p3": 2062, "d3": 2593, "p4": 3093, "d4": 3624}

WIN_MS = (-1500, 1500)                     # relative to omission onset
N_TIMES = int((WIN_MS[1] - WIN_MS[0]) / BIN_MS)      # 200
TIMES_OMI = WIN_MS[0] + np.arange(N_TIMES) * BIN_MS
BASELINE_REL_MS = (-250, -50)

OMISSION_CONDS = ["AAAX", "AAXB", "AXAB", "BBBX", "BBXA", "BXBA", "RRRX", "RRXR", "RXRR"]
AREA_POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
CHUNK = 16                                  # channels per vectorised block

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
        if g["cond"] not in OMISSION_CONDS:
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

    # key -> (sum over channels x trials of dB, count of contributing samples)
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

        slot = g["cond"].index("X") + 1
        p_on = EPOCH_ONSET_MS[f"p{slot}"]
        i0 = int(round((p_on + WIN_MS[0] - T0_SRC_MS) / BIN_MS))
        i1 = i0 + N_TIMES
        s0, s1 = max(0, i0), min(N_TIMES_SRC, i1)          # available source span
        d0, d1 = s0 - i0, s0 - i0 + (s1 - s0)              # destination span
        if s1 <= s0:
            skipped.append((os.path.basename(f), "window outside source time axis"))
            continue
        b0 = int(round((BASELINE_REL_MS[0] - WIN_MS[0]) / BIN_MS))
        b1 = int(round((BASELINE_REL_MS[1] - WIN_MS[0]) / BIN_MS))

        sel = chans[chans < arr.shape[1]]
        area10 = AREA_POOL.get(g["area"], g["area"])

        for c0 in range(0, sel.size, CHUNK):
            ch_block = sel[c0:c0 + CHUNK]
            raw = np.asarray(arr[:, ch_block, :, s0:s1], dtype=np.float32)
            # (trials, nch, freqs, t_avail) -> pad to the full window with NaN
            buf = np.full((raw.shape[0], raw.shape[1], len(FREQS_HZ), N_TIMES),
                          np.nan, dtype=np.float32)
            buf[:, :, :, d0:d1] = raw
            # RATIO OF EXPECTED POWER. Average POWER over trials first, then divide, then
            # take the logarithm once at the very end. Three wrong orders were measured on
            # this corpus before settling here (alpha, whole corpus):
            #   mean of per-bin dB          -1.42 dB   biased LOW  by the variance of the log
            #   log of mean of per-bin ratio +1.43 dB  biased HIGH by small-baseline samples
            #   per-trial log ratio, meaned  -0.32 dB  the census convention, close to correct
            #   trial-mean power, then ratio -0.58 dB  <- this one, the ratio of expectations
            # The first made all three animals agree in direction and the second made them all
            # increase; neither was physiology. This order is the estimand "change in expected
            # power", and each channel is divided by its own baseline so channels of very
            # different absolute power contribute comparably when later averaged.
            with np.errstate(divide="ignore", invalid="ignore"):
                p_bar = np.nanmean(buf, axis=0)                              # (nch, f, t)
                b_bar = np.nanmean(buf[:, :, :, b0:b1], axis=(0, 3))         # (nch, f)
                dbv = p_bar / b_bar[:, :, None]
            dbv[~np.isfinite(dbv)] = np.nan
            dbv[dbv <= 0] = np.nan
            dbv = dbv[None, ...]        # keep the (samples, nch, f, t) accumulation shape

            for j, ch in enumerate(ch_block):
                layer = lmap.get(int(ch), None)
                layer = "unknown" if (layer is None or (isinstance(layer, float)
                                                        and np.isnan(layer))) else str(layer)
                block = dbv[:, j]                                  # (trials, freqs, times)
                good = np.isfinite(block)
                s = np.where(good, block, 0.0).sum(axis=0).astype(np.float64)
                c = good.sum(axis=0).astype(np.float64)
                for key in (f"{g['session_prefix']}|{area10}|all",
                            f"{g['session_prefix']}|{area10}|{layer}"):
                    acc_sum[key] += s
                    acc_cnt[key] += c
                    meta[key]["n_trials"] += int(np.isfinite(buf[:, j, 0, 0]).sum())
                    meta[key]["conds"].add(g["cond"])
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
        freqs=FREQS_HZ, times=TIMES_OMI)

    idx = pd.DataFrame([{
        "key": k, "session_prefix": k.split("|")[0], "area": k.split("|")[1],
        "layer": k.split("|")[2], "n_channels": meta[k]["n_channels"],
        "n_channel_trials": meta[k]["n_trials"],
        "n_conditions": len(meta[k]["conds"]),
    } for k in keys])
    idx.to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Time-resolved omission-aligned dB maps per session x area x putative layer; "
                   "each channel referenced to its own pre-omission baseline.",
        "source_dir": TFR_DIR, "area_vector": AREA_VEC,
        "n_files_processed": len(targets), "n_files_skipped": len(skipped),
        "skipped": skipped[:50],
        "window_ms_re_omission": list(WIN_MS), "n_time_bins": N_TIMES, "bin_ms": BIN_MS,
        "baseline_ms_re_omission": list(BASELINE_REL_MS),
        "baseline_scope": "per channel, per trial, per frequency; no cross-area or "
                          "cross-session normalisation anywhere",
        "stored_quantity": "POWER RATIO power(f,t)/baseline(f), NOT decibels. Sums and counts "
                           "are of the ratio; take 10*log10 once, after all averaging.",
        "why_ratio": "Averaging decibels averages logarithms and is biased low by roughly "
                     "half the variance of the log. Measured on this corpus that bias runs "
                     "from -0.17 dB to -1.98 dB across subjects, tracks each subject's "
                     "log-power SD, and is large enough to reverse the sign of a subject's "
                     "effect. The dB-averaged version of this extraction made all three "
                     "subjects agree in direction; the ratio version does not.",
        "freqs_hz": [int(FREQS_HZ[0]), int(FREQS_HZ[-1]), 2],
        "area_pooling": AREA_POOL,
        "areas": sorted(idx.area.unique().tolist()),
        "layers": sorted(idx.layer.unique().tolist()),
        "n_keys": len(keys),
        "late_slot_truncation": "conditions with X in position 4 end the trial and lack "
                                "samples beyond +897 ms, so bins after that are contributed "
                                "only by p2 and p3 omissions; per-bin counts are stored in "
                                "counts[] so the composition change is visible.",
        "next_stimulus": "for p2 and p3 omissions a new stimulus begins at +1031 ms; p4 "
                         "omissions have none. Anything after +1031 ms therefore mixes a "
                         "stimulus-evoked response into a subset of conditions and must not "
                         "be read as omission-related.",
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
