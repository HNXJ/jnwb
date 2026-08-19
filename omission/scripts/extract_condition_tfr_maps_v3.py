r"""
v3, 2026-08-14: adds cross-trial-median artifact repair, absent from v2 and the original.

WHY
    User directive: "we gotta make sure we are excluding intervals with artifacts ; artifacts
    are sharp increase in power that across trials in the same condition are not present." v2
    (this file's non-v3 sibling) fixed the .npy->.npz corpus migration but carried forward zero
    trial-level artifact rejection from the original script -- every trial's power, including a
    trial with a sharp, single-trial power spike absent from the other trials of the same
    session x area x condition, was averaged into the trial-mean unmodified. That is exactly the
    TFR-domain artifact class omission.jnwb_ext.artifact_repair.repair_band_artifacts already exists to
    catch (promoted 2026-08-14 from context/figures/fig_v1_omission_band_dynamics/
    band_power_dynamics.py, where it was already used for a different figure but never applied
    here): per band, per (trial, time), a one-sided robust-z test against the cross-trial
    median trend, threshold TFR_Z_THRESH=6.0; flagged cells are replaced by the cross-trial
    median at that band/time (substitution, not exclusion -- the trial is kept, only the
    flagged interval is repaired), so a rare single-trial spike cannot drag the session mean the
    way it would were the trial simply averaged in raw.
    Applied ONCE per file across all of that file's selected channels (not per accumulation
    chunk), immediately after windowing and before the trial-mean/baseline-ratio/dB pipeline, so
    the per-band detection statistic uses the full channel set rather than a chunk-dependent
    subset. Per-file flagged fractions are logged (artifact_log) and rolled into receipt.json
    (n_files_with_flags, mean/max frac_flagged per band) rather than only living in stdout.
    Only this repair step and the receipt/log additions differ from v2; loading, channel-join,
    and dB-estimator logic are unchanged.

--- v2 docstring below, preserved for provenance ---

v2, 2026-08-14: rebuilds this extraction against the CURRENT TFR corpus, not the one
extract_condition_tfr_maps.py was written against. WRITTEN AS A NEW FILE per this project's
"preserve originals" working agreement -- the original is untouched and its (now-stale) output
is not overwritten in place.

WHY A NEW FILE, NOT A ONE-LINE FIX
    The original's 2026-08-04 receipt.json reads source_dir="D:/workspace/data/tfr_arrays" --
    a path context/PROJECT_STATE.md explicitly lists under "Superseded paths -- do not restore".
    That corpus was 1,236 raw, unscreened, full-128-channel .npy files. The current corpus
    (scripts/precompute_tfr_arrays_v2.py, begun 2026-08-11) is 970 .npz files, already reduced
    to each area's real channel subset AND a 1/f-quality-screened subset of those -- the
    channel axis is no longer the full probe, and the surviving channel identities are stored
    in the file's own "channels" array (original probe-channel indices, ascending), not
    recoverable by treating array position as raw channel number. This is a different data
    contract, not just a different file extension, so the loading and channel-attribution logic
    below is rewritten, not patched:
      - glob *.npz instead of *.npy; np.load(f) returns a keyed archive (accessed via
        d["power"]/d["channels"]), not a bare ndarray -- unlike the original's
        np.load(f, mmap_mode="r"), which assumed a raw-array .npy and does not apply to a
        (compressed) .npz the same way.
      - Channel selection no longer subsets a big raw array by an externally-known channel
        list (channel_area_vector.csv) at matching ARRAY POSITIONS; the array is already
        exactly that area's screened channels, in the order given by the file's own "channels"
        field. channel_area_vector.csv is still consulted, but only to intersect against what
        actually survived screening and to look up putative_layer per real channel number --
        never to index the array by position from the old channel list.
    Frequency/time axis conventions (FREQS_HZ, N_TIMES_SRC, T0_SRC_MS/BIN_MS) are unchanged
    between the two corpora and are reused as-is.

--- Original docstring below, preserved for provenance ---

Time-resolved TFR maps per session x area x putative layer, for the p2-omission-vs-real
comparison across all three condition families (R, A, B).
(RRXR added 2026-07-31 for a per-subject V182o band-trace supplement -- p3-omission alongside
the original p2-omission RXRR comparison; same extraction, same baseline, just one more
condition value pulled from files that already existed on disk. AXAB/AAAB/BXBA/BBBA added
2026-08-04 for the omission-vs-stimulus x {A,B,R}-family GLMM: A/B family p2-omission
(AXAB/BXBA) and p2-real (AAAB/BBBA) matched pairs are the same design RXRR/RRRR already gives
for R family.)

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
from jnwb import paths as _P
from omission.jnwb_ext.artifact_repair import repair_band_artifacts, DEFAULT_BANDS

TFR_DIR = _P.tfr_dir()
AREA_VEC = _P.REPO_ROOT / "outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/condition_tfr_maps_p1d1p2d2p3_v3"

FREQS_HZ = np.arange(3, 201, 2)
N_TIMES_SRC = 500
T0_SRC_MS, BIN_MS = -1000.0, 10.0

WIN_MS = (-500, 2593)                                # p1 onset to the p3/d3 boundary
N_TIMES = int(round((WIN_MS[1] - WIN_MS[0]) / BIN_MS))
TIMES = WIN_MS[0] + np.arange(N_TIMES) * BIN_MS
# The middle third of d1 (531-1031 ms), not a pre-trial baseline -- see module docstring.
BASELINE_MS = (706, 856)

# p2-omission-vs-real, matched across all three families: RXRR/RRRR (R), AXAB/AAAB (A),
# BXBA/BBBA (B). RRXR kept for the existing p3-omission (V182o) supplement, which is unrelated
# to the p2 GLMM design and still reads only its own two conditions.
CONDS = ["RXRR", "RRXR", "RRRR", "AXAB", "AAAB", "BXBA", "BBBA"]
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
    for f in sorted(glob.glob(os.path.join(TFR_DIR, "*.npz"))):
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

    artifact_log = []
    acc_sum = defaultdict(lambda: np.zeros((len(FREQS_HZ), N_TIMES)))
    acc_cnt = defaultdict(lambda: np.zeros((len(FREQS_HZ), N_TIMES)))
    meta = defaultdict(lambda: {"n_channels": 0, "n_trials": 0})
    t_start = time.time()

    for k, (f, g, chans, lmap) in enumerate(targets, 1):
        # v2: .npz is a keyed archive, not a raw array. Its channel axis is ALREADY restricted
        # to this area's real-channel + 1/f-quality-screened subset (precompute_tfr_arrays_v2.py)
        # -- "channels" gives the original probe-channel number at each array position, so
        # channel identity must be looked up through it, never assumed equal to array position.
        try:
            with np.load(f) as d:
                arr = d["power"]
                file_channels = np.asarray(d["channels"])
        except Exception as e:
            skipped.append((os.path.basename(f), f"load failed: {e}"))
            continue
        if arr.ndim != 4 or arr.shape[2] != len(FREQS_HZ) or arr.shape[3] != N_TIMES_SRC:
            skipped.append((os.path.basename(f), f"shape {arr.shape}"))
            continue
        if i0 < 0 or i1 > N_TIMES_SRC:
            skipped.append((os.path.basename(f), "window outside source time axis"))
            continue

        # Intersect channel_area_vector.csv's expected channel numbers (chans) against what
        # actually survived screening in THIS file (file_channels); sel/sel_pos stay aligned
        # (sel[i] is the real channel number stored at array position sel_pos[i]).
        keep = np.isin(file_channels, chans)
        sel_pos = np.nonzero(keep)[0]
        sel = file_channels[sel_pos]
        if sel.size == 0:
            skipped.append((os.path.basename(f), "no overlap between area_vector channels and file channels"))
            continue
        area10 = AREA_POOL.get(g["area"], g["area"])
        cond = g["cond"]

        # v3: cross-trial-median artifact repair (omission.jnwb_ext.artifact_repair.repair_band_artifacts),
        # applied ONCE per file across ALL of this file's selected channels (not per chunk) so
        # the per-band detection statistic (channel-mean band power per trial x time) uses the
        # full channel set's SNR rather than a chunk-dependent subset, before any chunking for
        # memory. See module docstring: this extraction previously had NO trial-level artifact
        # rejection at all -- a single trial with a sharp, condition-atypical power spike in one
        # band was averaged into the session mean unmodified.
        windowed = np.asarray(arr[:, sel_pos, :, i0:i1], dtype=np.float32)  # (trials,nch,f,t)
        windowed, frac_flagged_by_band = repair_band_artifacts(windowed, FREQS_HZ, band_ranges=DEFAULT_BANDS)
        if any(v > 0 for v in frac_flagged_by_band.values()):
            artifact_log.append({"file": os.path.basename(f), "frac_flagged_by_band": frac_flagged_by_band})

        for c0 in range(0, sel.size, CHUNK):
            ch_block = sel[c0:c0 + CHUNK]
            buf = windowed[:, c0:c0 + CHUNK]                                    # (trials,nch,f,t)
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
                   "each channel referenced to its own middle-of-d1 baseline. v2: rebuilt "
                   "against the post-2026-08-11 .npz TFR corpus (channel axis joined via each "
                   "file's own 'channels' array, not by array position). v3: adds cross-trial-"
                   "median artifact repair (omission.jnwb_ext.artifact_repair.repair_band_artifacts, "
                   "TFR_Z_THRESH=6.0, one-sided) per file before trial-averaging -- v2 and the "
                   "original had none. Supersedes outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz "
                   "(2026-08-04, superseded D:/workspace/data/tfr_arrays path) and "
                   "outputs/condition_tfr_maps_p1d1p2d2p3_v2/maps.npz (correct corpus, no "
                   "artifact repair).",
        "source_dir": str(TFR_DIR), "area_vector": str(AREA_VEC),
        "n_files_processed": len(targets), "n_files_skipped": len(skipped),
        "skipped": skipped[:50], "conditions": CONDS,
        "artifact_repair": {
            "method": "omission.jnwb_ext.artifact_repair.repair_band_artifacts",
            "z_thresh": 6.0, "bands": list(DEFAULT_BANDS.keys()),
            "n_files_with_any_flag": len(artifact_log),
            "n_files_total": len(targets),
            "mean_frac_flagged_by_band": {
                b: float(np.mean([e["frac_flagged_by_band"].get(b, 0.0) for e in artifact_log]))
                for b in DEFAULT_BANDS
            } if artifact_log else {b: 0.0 for b in DEFAULT_BANDS},
            "max_frac_flagged_by_band": {
                b: float(np.max([e["frac_flagged_by_band"].get(b, 0.0) for e in artifact_log]))
                for b in DEFAULT_BANDS
            } if artifact_log else {b: 0.0 for b in DEFAULT_BANDS},
            "sample_flagged_files": artifact_log[:20],
        },
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
