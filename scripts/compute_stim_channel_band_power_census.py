r"""
Per-channel REAL-STIMULUS band-power census, area-resolved and baseline-corrected -- the
matched counterpart to compute_channel_band_power_census_v2.py's omission census, built to
answer the same area x band question for "a real stimulus was there" instead of "it was
omitted."

WHY THIS EXISTS
    compute_channel_band_power_census_v2.py's db_mid_omirel measures power in the OMITTED slot
    relative to the delay immediately before it. There was no channel-level equivalent for a
    REAL stimulus presentation, so fig05's area x band GLMM could not be asked "does the same
    area hierarchy hold for a genuine visual stimulus, not just for the absence of one." This
    fills that gap with the identical measure, window, and baseline convention -- same channel
    selection (area vector), same 5 bands, same -250..-50 ms pre-onset baseline -- so the two
    censuses are directly comparable, not just similarly-shaped.

CONDITIONS / SLOTS
    STIM_CONDS = RRRR, AAAB, BBBA -- the three families' no-early-omission control conditions,
    which have a REAL stimulus at every slot. Each file is read once per SLOT in (2, 3, 4) --
    matching the omission census's coverage exactly (GLO_CONDITIONS never omits p1, so the
    omission side never has a p1 window either; excluded here for the same reason, and to keep
    the two censuses' slot-position distributions identical).

MEASURE (identical convention to compute_channel_band_power_census_v2.py)
    db_stim_baserel = 10*log10(mean power in the stimulus window / mean power in the
    -250..-50 ms pre-stimulus-onset window), per trial per channel, averaged across trials.
    Only channels the per-channel area vector assigns to the file's area token contribute
    (same aliasing fix as v2).

OUTPUT
    outputs/lfp_band_census_stim/channel_band_power.csv.gz
    outputs/lfp_band_census_stim/receipt.json
"""
from __future__ import annotations

import glob
import json
import os
import platform
import re
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from jnwb import paths as _P
from jnwb.connectivity import CANONICAL_BANDS as BANDS

TFR_DIR = _P.tfr_dir()
AREA_VEC = _P.REPO_ROOT / "outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/lfp_band_census_stim"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES = 500
T0_MS, BIN_MS = -1000.0, 10.0
TIMES_MS = T0_MS + np.arange(N_TIMES) * BIN_MS

EPOCH_ONSET_MS = {"fx": -500, "p1": 0, "d1": 531, "p2": 1031, "d2": 1562,
                  "p3": 2062, "d3": 2593, "p4": 3093, "d4": 3624}
STIM_MS, DELAY_MS = 531, 500


BASELINE_REL_MS = (-250, -50)         # relative to the stimulus onset -- matches the
                                       # omission census's OMI_BASELINE_REL_MS exactly
STIM_CONDS = ["RRRR", "AAAB", "BBBA"]
STIM_SLOTS = (2, 3, 4)                 # matches the omission census's slot coverage (no p1)

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def ms_to_idx(ms: float) -> int:
    return int(round((ms - T0_MS) / BIN_MS))


def band_slice(lo_hz, hi_hz):
    m = np.where((FREQS_HZ >= lo_hz) & (FREQS_HZ < hi_hz))[0]
    return m[0], m[-1] + 1


def mean_power(arr_mm, chans, t_lo, t_hi, f0, f1):
    i0, i1 = max(0, ms_to_idx(t_lo)), min(N_TIMES, ms_to_idx(t_hi))
    if i1 <= i0:
        return None
    block = np.asarray(arr_mm[:, chans, f0:f1, i0:i1], dtype=np.float64)
    return block.mean(axis=(2, 3))


def db(num, den):
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 10.0 * np.log10(num / den)
    return np.where(np.isfinite(num) & (num > 0) & np.isfinite(den) & (den > 0), out, np.nan)


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(AREA_VEC):
        sys.exit(f"missing {AREA_VEC} -- run scripts/build_channel_area_vector.py first")
    av = pd.read_csv(AREA_VEC)

    seg, lay = {}, {}
    for (sp, pl, a), g in av.groupby(["session_prefix", "probe_letter", "area"]):
        g = g.sort_values("channel")
        seg[(sp, pl, a)] = g["channel"].to_numpy()
        if "putative_layer" in g.columns:
            lay[(sp, pl, a)] = dict(zip(g["channel"], g["putative_layer"]))

    files = sorted(glob.glob(os.path.join(TFR_DIR, "*.npy")))
    targets, skipped = [], []
    for f in files:
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if not m:
            continue
        g = m.groupdict()
        if g["cond"] not in STIM_CONDS:
            continue
        g["session_prefix"] = f"sub-{g['subject']}_ses-{g['session']}"
        key = (g["session_prefix"], g["probe"], g["area"])
        if key not in seg:
            skipped.append((os.path.basename(f), "no channel segment for area token"))
            continue
        targets.append((f, g, seg[key]))
    if limit:
        targets = targets[:limit]

    print(f"[{datetime.now():%H:%M:%S}] {len(targets)} stim files x {len(STIM_SLOTS)} slots "
         f"({len(skipped)} skipped)", flush=True)

    band_idx = {b: band_slice(*hz) for b, hz in BANDS.items()}
    recs = []
    t0 = time.time()

    for k, (f, g, chans) in enumerate(targets, 1):
        try:
            a = np.load(f, mmap_mode="r")
        except Exception as e:
            skipped.append((os.path.basename(f), f"load failed: {e}"))
            continue
        if a.ndim != 4 or a.shape[2] != len(FREQS_HZ) or a.shape[3] != N_TIMES:
            skipped.append((os.path.basename(f), f"unexpected shape {a.shape}"))
            continue
        sel = chans[chans < a.shape[1]]
        if sel.size == 0:
            skipped.append((os.path.basename(f), "segment outside array channel range"))
            continue

        lmap = lay.get((g["session_prefix"], g["probe"], g["area"]), {})

        for slot in STIM_SLOTS:
            p_on = EPOCH_ONSET_MS[f"p{slot}"]
            mid = (p_on, p_on + STIM_MS)
            base = (p_on + BASELINE_REL_MS[0], p_on + BASELINE_REL_MS[1])

            for band, (f0, f1) in band_idx.items():
                p_mid = mean_power(a, sel, *mid, f0, f1)
                p_base = mean_power(a, sel, *base, f0, f1)
                if p_mid is None or p_base is None:
                    continue
                d_stim = db(p_mid, p_base)
                n_ok = np.sum(np.isfinite(d_stim), axis=0)
                with np.errstate(invalid="ignore"):
                    m_stim = np.nanmean(d_stim, axis=0)
                    s_stim = (np.nanstd(d_stim, axis=0, ddof=1) if d_stim.shape[0] > 1
                             else np.full(sel.size, np.nan))

                for j, ch in enumerate(sel):
                    if n_ok[j] == 0:
                        continue
                    recs.append({
                        "subject": g["subject"], "session": g["session"],
                        "session_prefix": g["session_prefix"], "probe": g["probe"],
                        "area": g["area"], "cond": g["cond"], "stim_slot": slot,
                        "channel": int(ch), "putative_layer": lmap.get(int(ch), None),
                        "band": band, "n_trials": int(n_ok[j]),
                        "db_stim_baserel": float(m_stim[j]),
                        "db_stim_baserel_sd": float(s_stim[j]),
                    })

        if k % 50 == 0:
            print(f"[{datetime.now():%H:%M:%S}]  {k}/{len(targets)} files, "
                 f"{len(recs):,} rows, {time.time()-t0:.0f}s", flush=True)

    df = pd.DataFrame(recs)
    out = os.path.join(OUT_DIR, "channel_band_power.csv.gz")
    df.to_csv(out, index=False, compression="gzip")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Real-stimulus counterpart to compute_channel_band_power_census_v2.py's "
                  "omission census -- same measure/window/baseline convention, stimulus "
                  "conditions instead of omission conditions.",
        "area_vector": AREA_VEC, "source_dir": TFR_DIR,
        "stim_conds": STIM_CONDS, "stim_slots": list(STIM_SLOTS),
        "n_files_total": len(files), "n_files_stim_processed": len(targets),
        "n_files_skipped": len(skipped), "skipped": skipped[:50],
        "baseline_rel_ms": list(BASELINE_REL_MS),
        "bands_hz": {k: list(v) for k, v in BANDS.items()},
        "measure": "10*log10(mean power in the stimulus window / mean power in the "
                  "-250..-50 ms pre-stimulus-onset window), per trial per channel, then "
                  "averaged across trials",
        "channel_selection": "only channels assigned to the file's area token by the "
                             "per-channel area vector",
        "n_rows": int(len(df)),
        "areas": sorted(df["area"].unique().tolist()) if len(df) else [],
        "n_sessions": int(df["session_prefix"].nunique()) if len(df) else 0,
        "subjects": sorted(df["subject"].unique().tolist()) if len(df) else [],
        "median_trials_per_channel": float(df["n_trials"].median()) if len(df) else None,
        "runtime_s": round(time.time() - t0, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(f"\nWROTE {out}  ({len(df):,} rows)")
    print(f"areas={receipt['areas']}  sessions={receipt['n_sessions']}  "
         f"runtime={receipt['runtime_s']}s")
    return df


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
