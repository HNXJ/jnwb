r"""
Step 3c -- per-channel omission band-power census, area-resolved and baseline-corrected.

SUPERSEDES scripts/compute_real_channel_band_power_census.py. Two changes, both material:

1. AREA ALIASING FIXED. The previous run read all 128 channels of every file. Because
   precompute_tfr_arrays.py writes the SAME full-probe array once per area token, a
   dual-area probe contributed its entire channel set to BOTH areas -- so any between-area
   comparison was partly a probe against itself. This version selects only the channels
   the per-channel area vector assigns to the file's area token
   (outputs/channel_area_vector/channel_area_vector.csv, built by build_channel_area_vector.py).

2. BASELINE CHANGED TO THE OMISSION-RELATIVE WINDOW. The previous run used the pre-trial
   fixation window (-500 to -50 ms re: p1). The manuscript Methods specify -250 to -50 ms
   relative to the OMISSION onset, i.e. the late part of the delay immediately preceding
   the omitted slot. Both are computed here, because they answer different questions:

     db_mid_omirel  -- middle o vs the late preceding delay. The manuscript's primary
                       measure. Conservative: baseline and signal are visually identical
                       screens ~250 ms apart, so slow drift and arousal are differenced out.
                       It is NOT a change from a neutral pre-trial state; it is a change
                       relative to the first of the three empty periods.
     db_mid_fxrel   -- middle o vs the pre-trial fixation window. Answers "is power during
                       the omission different from before the trial", but is contaminated by
                       up to 3.6 s of within-trial drift for late omission slots.

   Reporting only one of these would hide the distinction. Both are emitted per channel.

PARADIGM
    trial = fx - p1 - d1 - p2 - d2 - p3 - d3 - p4 - d4 ; p1..p4 carry stimulus identity,
    fx and d1..d4 are gray screen + fixation dot, VISUALLY IDENTICAL to an omission (X).
    RRXR renders as  o R o R o|o|o R o  -- the omission window is d2 + p3(X) + d3, three
    consecutive identical empty periods. The MIDDLE o is the omitted slot itself.

    H0: in each band, at each channel, power in the middle o does not differ from baseline.
    H1: at least one band shows a significant change.

ARRAY CONTRACT (verified)
    D:/workspace/data/tfr_arrays/sub-<subj>_ses-<sess>-<probe>-<area>-<cond>.npy
    (trials, 128 channels, 99 freqs, 500 times) float32, RAW power,
    freqs = arange(3,201,2) Hz, times = -1000 + arange(500)*10 ms, p1-aligned.

OUTPUTS
    outputs/lfp_band_census_v2/channel_band_power.csv.gz
    outputs/lfp_band_census_v2/receipt.json
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
from jnwb.spectral import CANONICAL_BANDS as BANDS, to_db

TFR_DIR = _P.tfr_dir()
AREA_VEC = _P.REPO_ROOT / "outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/lfp_band_census_v2"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES = 500
T0_MS, BIN_MS = -1000.0, 10.0
TIMES_MS = T0_MS + np.arange(N_TIMES) * BIN_MS

EPOCH_ONSET_MS = {"fx": -500, "p1": 0, "d1": 531, "p2": 1031, "d2": 1562,
                  "p3": 2062, "d3": 2593, "p4": 3093, "d4": 3624}
STIM_MS, DELAY_MS = 531, 500

OMI_BASELINE_REL_MS = (-250, -50)     # relative to omission onset (manuscript Methods)
FX_BASELINE_MS = (-500, -50)          # pre-trial fixation, p1-relative (secondary)

OMISSION_CONDS = ["AAAX", "AAXB", "AXAB", "BBBX", "BBXA", "BXBA", "RRRX", "RRXR", "RXRR"]

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def ms_to_idx(ms: float) -> int:
    return int(round((ms - T0_MS) / BIN_MS))


def band_slice(lo_hz: float, hi_hz: float):
    m = np.where((FREQS_HZ >= lo_hz) & (FREQS_HZ < hi_hz))[0]
    return m[0], m[-1] + 1


def windows(cond: str):
    """(mid, flank_a, flank_b, omission_baseline) in ms, p1-aligned."""
    slot = cond.index("X") + 1
    p_on = EPOCH_ONSET_MS[f"p{slot}"]
    mid = (p_on, p_on + STIM_MS)
    pre = EPOCH_ONSET_MS[f"d{slot - 1}"]                    # slot >= 2 for every omission cond
    flank_a = (pre, pre + DELAY_MS)
    post = EPOCH_ONSET_MS[f"d{slot}"]
    flank_b = (post, min(post + DELAY_MS, TIMES_MS[-1]))
    base = (p_on + OMI_BASELINE_REL_MS[0], p_on + OMI_BASELINE_REL_MS[1])
    return mid, flank_a, flank_b, base


def mean_power(arr_mm, chans, t_lo, t_hi, f0, f1):
    """Mean raw power over [t_lo,t_hi) x band for selected channels -> (trials, n_sel)."""
    i0, i1 = max(0, ms_to_idx(t_lo)), min(N_TIMES, ms_to_idx(t_hi))
    if i1 <= i0:
        return None
    block = np.asarray(arr_mm[:, chans, f0:f1, i0:i1], dtype=np.float64)
    return block.mean(axis=(2, 3))


def db(num, den):
    with np.errstate(divide="ignore", invalid="ignore"):
        out = to_db(num / den)
    return np.where(np.isfinite(num) & (num > 0) & np.isfinite(den) & (den > 0), out, np.nan)


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(AREA_VEC):
        sys.exit(f"missing {AREA_VEC} -- run scripts/build_channel_area_vector.py first")
    av = pd.read_csv(AREA_VEC)

    # (session_prefix, probe_letter, area) -> sorted channel indices, and -> layer labels
    seg = {}
    lay = {}
    for (sp, pl, a), g in av.groupby(["session_prefix", "probe_letter", "area"]):
        g = g.sort_values("channel")
        seg[(sp, pl, a)] = g["channel"].to_numpy()
        if "putative_layer" in g.columns:
            lay[(sp, pl, a)] = dict(zip(g["channel"], g["putative_layer"]))

    # Two on-disk formats coexist: the legacy full-128-channel-padded .npy (array indexed
    # directly by raw probe-channel 0-127) and the 2026-08-11 compressed .npz (real per-area
    # channel subset + 1/f quality screen, see scripts/precompute_tfr_arrays_v2.py; array's
    # channel axis is a SUBSET, real raw-channel ids carried in the "channels" key). Prefer
    # .npz when both exist for the same (session,probe,area,cond) -- it is the corrected,
    # doctrine-compliant regeneration; a stale .npy should not silently win by glob order.
    npy_files = glob.glob(os.path.join(TFR_DIR, "*.npy"))
    npz_files = glob.glob(os.path.join(TFR_DIR, "*.npz"))
    by_stem = {os.path.basename(f)[:-4]: ("npy", f) for f in npy_files}
    for f in npz_files:
        by_stem[os.path.basename(f)[:-4]] = ("npz", f)  # npz wins on collision
    files = sorted(f for _, f in by_stem.values())

    targets, skipped = [], []
    for stem, (fmt, f) in sorted(by_stem.items()):
        m = FNAME_RE.match(stem)
        if not m:
            skipped.append((os.path.basename(f), "unparsed filename"))
            continue
        g = m.groupdict()
        if g["cond"] not in OMISSION_CONDS:
            continue
        g["session_prefix"] = f"sub-{g['subject']}_ses-{g['session']}"
        key = (g["session_prefix"], g["probe"], g["area"])
        if key not in seg:
            skipped.append((os.path.basename(f), "no channel segment for area token"))
            continue
        targets.append((f, fmt, g, seg[key]))
    if limit:
        targets = targets[:limit]

    print(f"[{datetime.now():%H:%M:%S}] {len(targets)} omission files "
          f"({len(skipped)} skipped)", flush=True)

    band_idx = {b: band_slice(*hz) for b, hz in BANDS.items()}
    recs = []
    t0 = time.time()

    for k, (f, fmt, g, chans) in enumerate(targets, 1):
        try:
            if fmt == "npz":
                npz = np.load(f)
                a = npz["power"]                 # (trials, n_kept, freqs, times), already
                                                  # real-per-area + 1/f-screened at write time
                raw_ch = npz["channels"]         # raw probe-channel id per array column
            else:
                a = np.load(f, mmap_mode="r")    # legacy full-128-channel array
                raw_ch = np.arange(a.shape[1])
        except Exception as e:
            skipped.append((os.path.basename(f), f"load failed: {e}"))
            continue
        if a.ndim != 4 or a.shape[2] != len(FREQS_HZ) or a.shape[3] != N_TIMES:
            skipped.append((os.path.basename(f), f"unexpected shape {a.shape}"))
            continue
        if fmt == "npz":
            # Array columns are already exactly this area's real, quality-screened channels
            # (scripts/precompute_tfr_arrays_v2.py) -- use all of them, local index == column.
            sel = np.arange(a.shape[1])
            sel_raw_ids = raw_ch
        else:
            # Legacy full-128 array: chans (from channel_area_vector) ARE direct column
            # indices into the 128-wide array.
            sel = chans[chans < a.shape[1]]
            sel_raw_ids = sel
        if sel.size == 0:
            skipped.append((os.path.basename(f), "segment outside array channel range"))
            continue

        mid, fa, fb, obase = windows(g["cond"])
        lmap = lay.get((g["session_prefix"], g["probe"], g["area"]), {})

        for band, (f0, f1) in band_idx.items():
            p_mid = mean_power(a, sel, *mid, f0, f1)
            p_ob = mean_power(a, sel, *obase, f0, f1)
            p_fx = mean_power(a, sel, *FX_BASELINE_MS, f0, f1)
            p_fa = mean_power(a, sel, *fa, f0, f1)
            p_fb = mean_power(a, sel, *fb, f0, f1)
            if p_mid is None or p_ob is None or p_fx is None:
                continue

            # P0 FIX (2026-08-11, artifacts/.lab/fig05-p0-dB-averaging-fix-20260811.json):
            # the point estimate must average POWER over trials first, divide by the
            # baseline, and take 10*log10 exactly once -- never average per-trial dB values.
            # Averaging decibels subtracts a term proportional to the variance of the log,
            # biasing a noisier session/channel low relative to a quieter one (measured
            # elsewhere on this corpus at -0.17 to -1.98 dB, large enough to reverse an
            # animal's sign -- see artifacts/.lab/db_averaging_bias_finding_20260728.json).
            # The previous implementation here did exactly that: db(p_mid, p_ob) computed a
            # per-trial ratio+log, then nanmean averaged the resulting dB values across
            # trials. Fixed by averaging p_mid/p_ob/p_fx/p_fa/p_fb over trials FIRST, then
            # taking the log once on the trial-averaged power.
            n_ok = np.sum(np.isfinite(p_mid) & np.isfinite(p_ob), axis=0)
            with np.errstate(invalid="ignore"):
                mp_mid = np.nanmean(p_mid, axis=0)
                mp_ob = np.nanmean(p_ob, axis=0)
                mp_fx = np.nanmean(p_fx, axis=0)
                mp_fa = np.nanmean(p_fa, axis=0)
                mp_fb = np.nanmean(p_fb, axis=0)

            m_omi = db(mp_mid, mp_ob)                     # primary -- ratio-then-log-once
            m_fx = db(mp_mid, mp_fx)                      # secondary -- same order
            m_flank = np.nanmean(np.stack([db(mp_fa, mp_fx), db(mp_fb, mp_fx)]), axis=0)

            # Descriptive-only trial-to-trial dispersion of the per-trial dB ratio -- NOT the
            # source of the point estimate above, and not fed into the GLMM (RESP uses only
            # db_mid_omirel). Retained because the previous receipt exposed a "_sd" column;
            # kept for continuity, explicitly labeled as descriptive.
            with np.errstate(invalid="ignore"):
                d_omi_descriptive = db(p_mid, p_ob)
                s_omi = (np.nanstd(d_omi_descriptive, axis=0, ddof=1)
                         if d_omi_descriptive.shape[0] > 1 else np.full(sel.size, np.nan))

            for j, ch in enumerate(sel_raw_ids):
                if n_ok[j] == 0:
                    continue
                recs.append({
                    "subject": g["subject"], "session": g["session"],
                    "session_prefix": g["session_prefix"], "probe": g["probe"],
                    "area": g["area"], "cond": g["cond"],
                    "omitted_slot": g["cond"].index("X") + 1,
                    "channel": int(ch), "putative_layer": lmap.get(int(ch), None),
                    "band": band, "n_trials": int(n_ok[j]),
                    "db_mid_omirel": float(m_omi[j]),
                    # Descriptive trial-to-trial dispersion of the per-trial dB ratio; consumed
                    # downstream (scripts/extract_within_session_lfp_lfp_sliding_corr.py,
                    # scripts/smoke_test_sliding_trial_correlation.py) as a per-channel t-like
                    # SNR denominator -- kept under its original name for that consumer contract.
                    # NOT the source of db_mid_omirel above (see P0 fix comment).
                    "db_mid_omirel_sd": float(s_omi[j]),
                    "db_mid_fxrel": float(m_fx[j]), "db_flank_fxrel": float(m_flank[j]),
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
        "supersedes": "scripts/compute_real_channel_band_power_census.py "
                      "(all-128-channel read, p1-relative fx baseline)",
        "area_vector": str(AREA_VEC),
        "source_dir": str(TFR_DIR),
        "n_files_total": len(files), "n_files_omission_processed": len(targets),
        "n_files_skipped": len(skipped), "skipped": skipped[:50],
        "array_contract": {"axes": "(trials, channels, freqs, times)",
                           "freqs_hz": "arange(3,201,2)", "times_ms": "-1000 + arange(500)*10",
                           "values": "raw power (not baseline-normalized)"},
        "epoch_onsets_ms": EPOCH_ONSET_MS, "stim_ms": STIM_MS, "delay_ms": DELAY_MS,
        "bands_hz": {k: list(v) for k, v in BANDS.items()},
        "baselines": {
            "primary_omission_relative_ms": list(OMI_BASELINE_REL_MS),
            "primary_note": "relative to omission onset; falls inside the delay immediately "
                            "preceding the omitted slot, which is itself one of the three "
                            "visually identical empty periods",
            "secondary_fx_ms_p1_relative": list(FX_BASELINE_MS),
        },
        "measures": {
            "db_mid_omirel": "10*log10(trial-averaged power in the omitted slot / "
                             "trial-averaged power in the omission-relative baseline), per "
                             "channel -- power averaged over trials FIRST, log taken ONCE "
                             "(P0 fix 2026-08-11, see "
                             "artifacts/.lab/fig05-p0-dB-averaging-fix-20260811.json; "
                             "previously averaged per-trial dB values, which is the biased "
                             "anti-pattern documented in db_averaging_bias_finding_20260728.json)",
            "db_mid_omirel_sd": "descriptive dispersion of the per-trial dB ratio across "
                                "trials; NOT the source of db_mid_omirel and not used by the "
                                "fig05 GLMM -- retained for the t-like SNR statistic consumed "
                                "by scripts/extract_within_session_lfp_lfp_sliding_corr.py",
            "db_mid_fxrel": "same numerator, pre-trial fixation denominator, same "
                            "trial-averaged-power-then-log-once order",
            "db_flank_fxrel": "mean of the two flanking delays vs the fixation baseline, same "
                              "order",
        },
        "channel_selection": "only channels assigned to the file's area token by the "
                             "per-channel area vector; this is the aliasing fix",
        "n_rows": int(len(df)),
        "areas": sorted(df["area"].unique().tolist()) if len(df) else [],
        "n_sessions": int(df["session_prefix"].nunique()) if len(df) else 0,
        "subjects": sorted(df["subject"].unique().tolist()) if len(df) else [],
        "median_trials_per_channel": float(df["n_trials"].median()) if len(df) else None,
        "layer_coverage_fraction": (round(float(df["putative_layer"].notna().mean()), 4)
                                    if len(df) else 0.0),
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
