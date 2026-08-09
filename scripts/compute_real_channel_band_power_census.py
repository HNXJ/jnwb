r"""
Real per-channel TFR band-power census for omission windows.

Replaces the hardcoded literals in scripts/archive_oneoff/compute_empirical_census_and_power.py
(see artifacts/.lab/census_provenance_synthetic_finding_20260728.json).

PARADIGM (Hamm, 2026-07-28)
    A trial is  fx - p1 - d1 - p2 - d2 - p3 - d3 - p4 - d4
    p1..p4 carry stimulus identity; fx and d1..d4 are gray screen + fixation dot and are
    VISUALLY IDENTICAL to an omission (X). So RRXR renders as

        o - R - o - R - o - o - o - R - o
                          \_______/
                       omission window = d2 + p3(X) + d3
                       three consecutive visually identical empty periods

    The MIDDLE o (the omitted stimulus slot itself) carries the omission signature.

HYPOTHESES
    H0: at each channel, in each band, spectral power during the three o's is flat --
        no significant change from the pre-trial fixation baseline.
    H1: in at least one band there is a significant positive or negative change.

WINDOWS (p1-aligned, ms; from artifacts/.lab/domain-paradigm-timing-layout.json)
    fx=-500 p1=0 d1=531 p2=1031 d2=1562 p3=2062 d3=2593 p4=3093 d4=3624
    stimulus 531 ms, delay 500 ms

ARRAY CONTRACT (verified against scripts/archive_oneoff/precompute_tfr_arrays.py)
    D:/workspace/data/tfr_arrays/sub-<subj>_ses-<sess>-<probe>-<area>-<cond>.npy
    shape (trials, 128 channels, 99 freqs, 500 times), float32, RAW POWER (not normalized)
    freqs = arange(3, 201, 2) Hz ; times = -1000 + arange(500)*10 ms

OUTPUTS
    outputs/lfp_band_census/channel_band_power.parquet   per channel x band x condition
    outputs/lfp_band_census/receipt.json                 provenance + parameters + counts

V3 IS NOT COLLAPSED. V3, V3a and V3d are kept as separate areas, unlike
map_area_canonical() in the archived script which merged them into "V3a-d-v".
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

TFR_DIR = _P.tfr_dir()
OUT_DIR = _P.REPO_ROOT / "outputs/lfp_band_census"

FREQS_HZ = np.arange(3, 201, 2)          # 99 bins
N_TIMES = 500
T0_MS, BIN_MS = -1000.0, 10.0
TIMES_MS = T0_MS + np.arange(N_TIMES) * BIN_MS

EPOCH_ONSET_MS = {"fx": -500, "p1": 0, "d1": 531, "p2": 1031, "d2": 1562,
                  "p3": 2062, "d3": 2593, "p4": 3093, "d4": 3624}
STIM_MS, DELAY_MS = 531, 500

BANDS = {"theta": (4, 8), "alpha": (8, 14), "beta": (14, 30),
         "low_gamma": (30, 50), "high_gamma": (50, 80)}

BASELINE_MS = (-500, -50)                # fx window, trimmed to avoid wavelet edge at p1 onset

# conditions carrying an omission; X position gives the omitted slot (1-indexed)
OMISSION_CONDS = ["AAAX", "AAXB", "AXAB", "BBBX", "BBXA", "BXBA", "RRRX", "RRXR", "RXRR"]
CONTROL_CONDS = ["AAAB", "BBBA", "RRRR"]

FNAME_RE = re.compile(r"^sub-(?P<subject>.+?)_ses-(?P<session>.+?)-(?P<probe>[A-Z])-"
                      r"(?P<area>.+)-(?P<cond>[A-Z]+)$")


def ms_to_idx(ms: float) -> int:
    return int(round((ms - T0_MS) / BIN_MS))


def band_slice(lo_hz: float, hi_hz: float):
    m = np.where((FREQS_HZ >= lo_hz) & (FREQS_HZ < hi_hz))[0]
    return m[0], m[-1] + 1


def omission_windows(cond: str):
    """Return (middle_o, flank_a, flank_b) windows in ms for an omission condition."""
    slot = cond.index("X") + 1
    p_on = EPOCH_ONSET_MS[f"p{slot}"]
    mid = (p_on, p_on + STIM_MS)
    pre = EPOCH_ONSET_MS[f"d{slot - 1}"] if slot > 1 else EPOCH_ONSET_MS["fx"]
    flank_a = (pre, pre + DELAY_MS)
    post = EPOCH_ONSET_MS[f"d{slot}"]
    flank_b = (post, min(post + DELAY_MS, TIMES_MS[-1]))
    return mid, flank_a, flank_b


def mean_power(arr_mm, t_lo_ms, t_hi_ms, f0, f1):
    """Mean raw power over [t_lo,t_hi) x band -> (trials, channels). Windowed memmap read."""
    i0, i1 = ms_to_idx(t_lo_ms), ms_to_idx(t_hi_ms)
    i0, i1 = max(0, i0), min(N_TIMES, i1)
    if i1 <= i0:
        return None
    block = np.asarray(arr_mm[:, :, f0:f1, i0:i1], dtype=np.float64)
    return block.mean(axis=(2, 3))


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(TFR_DIR, "*.npy")))
    recs, skipped = [], []
    t_start = time.time()

    targets = []
    for f in files:
        m = FNAME_RE.match(os.path.basename(f)[:-4])
        if not m:
            skipped.append((os.path.basename(f), "unparsed filename"))
            continue
        if m.group("cond") not in OMISSION_CONDS:
            continue
        targets.append((f, m.groupdict()))
    if limit:
        targets = targets[:limit]

    print(f"[{datetime.now():%H:%M:%S}] {len(targets)} omission-condition files to process",
          flush=True)

    band_idx = {b: band_slice(*hz) for b, hz in BANDS.items()}

    for k, (f, meta) in enumerate(targets, 1):
        try:
            a = np.load(f, mmap_mode="r")
        except Exception as e:
            skipped.append((os.path.basename(f), f"load failed: {e}"))
            continue
        if a.ndim != 4 or a.shape[2] != len(FREQS_HZ) or a.shape[3] != N_TIMES:
            skipped.append((os.path.basename(f), f"unexpected shape {a.shape}"))
            continue

        n_trials, n_ch = a.shape[0], a.shape[1]
        mid, fa, fb = omission_windows(meta["cond"])

        for band, (f0, f1) in band_idx.items():
            base = mean_power(a, *BASELINE_MS, f0, f1)
            mo = mean_power(a, *mid, f0, f1)
            ka = mean_power(a, *fa, f0, f1)
            kb = mean_power(a, *fb, f0, f1)
            if base is None or mo is None:
                continue

            valid = np.isfinite(base) & (base > 0) & np.isfinite(mo) & (mo > 0)
            with np.errstate(divide="ignore", invalid="ignore"):
                db_mid = 10.0 * np.log10(mo / base)
                db_fa = 10.0 * np.log10(ka / base) if ka is not None else np.full_like(db_mid, np.nan)
                db_fb = 10.0 * np.log10(kb / base) if kb is not None else np.full_like(db_mid, np.nan)
            db_mid = np.where(valid, db_mid, np.nan)

            # channel-level summary across trials
            with np.errstate(invalid="ignore"):
                m_mid = np.nanmean(db_mid, axis=0)
                s_mid = np.nanstd(db_mid, axis=0, ddof=1) if n_trials > 1 else np.full(n_ch, np.nan)
                m_flank = np.nanmean(np.stack([db_fa, db_fb]), axis=(0, 1))
                n_ok = np.sum(np.isfinite(db_mid), axis=0)

            for ch in range(n_ch):
                if n_ok[ch] == 0:
                    continue
                recs.append({
                    "subject": meta["subject"], "session": meta["session"],
                    "probe": meta["probe"], "area": meta["area"], "cond": meta["cond"],
                    "omitted_slot": meta["cond"].index("X") + 1,
                    "channel": ch, "band": band,
                    "n_trials": int(n_ok[ch]),
                    "db_mid": float(m_mid[ch]),
                    "db_mid_sd": float(s_mid[ch]),
                    "db_flank": float(m_flank[ch]),
                    "db_mid_minus_flank": float(m_mid[ch] - m_flank[ch]),
                })

        if k % 50 == 0:
            print(f"[{datetime.now():%H:%M:%S}]  {k}/{len(targets)} files, "
                  f"{len(recs):,} rows, {time.time()-t_start:.0f}s", flush=True)

    df = pd.DataFrame(recs)
    out_parquet = os.path.join(OUT_DIR, "channel_band_power.csv.gz")
    df.to_csv(out_parquet, index=False, compression="gzip")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Real per-channel band-power census replacing hardcoded literals in "
                   "scripts/archive_oneoff/compute_empirical_census_and_power.py",
        "source_dir": TFR_DIR,
        "n_files_total": len(files),
        "n_files_omission": len(targets),
        "n_files_skipped": len(skipped),
        "skipped": skipped[:50],
        "array_contract": {
            "axes": "(trials, channels, freqs, times)",
            "freqs_hz": "arange(3, 201, 2)", "n_freqs": len(FREQS_HZ),
            "times_ms": "-1000 + arange(500)*10", "n_times": N_TIMES,
            "values": "raw power (not baseline-normalized)",
        },
        "epoch_onsets_ms": EPOCH_ONSET_MS,
        "stim_ms": STIM_MS, "delay_ms": DELAY_MS,
        "baseline_ms": list(BASELINE_MS),
        "bands_hz": {k: list(v) for k, v in BANDS.items()},
        "measure": "db = 10*log10(mean_power(window) / mean_power(baseline)), per trial per "
                   "channel, then averaged across trials",
        "middle_o_definition": "the omitted stimulus slot itself (p<slot>), the central of the "
                               "three consecutive visually identical empty periods",
        "flank_definition": "the two delay periods immediately flanking the omitted slot; "
                            "visually identical to it, used as a within-trial control",
        "v3_handling": "V3, V3a, V3d kept SEPARATE (not collapsed to V3a-d-v)",
        "n_rows": int(len(df)),
        "areas": sorted(df["area"].unique().tolist()) if len(df) else [],
        "sessions": int(df["session"].nunique()) if len(df) else 0,
        "subjects": sorted(df["subject"].unique().tolist()) if len(df) else [],
        "channel_condition_band_rows": int(len(df)),
        "runtime_s": round(time.time() - t_start, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(f"\nWROTE {out_parquet}  ({len(df):,} rows)")
    print(f"WROTE {os.path.join(OUT_DIR, 'receipt.json')}")
    print(f"runtime {receipt['runtime_s']}s  areas={receipt['areas']}")
    return df


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=lim)
