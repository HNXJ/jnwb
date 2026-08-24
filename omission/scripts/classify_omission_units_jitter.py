r"""
Omission unit classification against a temporal-jitter null, plus response-onset latency.

DEFINITION (Hamm, 2026-07-28)
    The omitted slot spans [x, x + 531] ms. The null displaces that window by
    D ~ Uniform(-200, +200) ms. Each shuffle therefore asks whether the firing in the
    omitted slot differs from firing at a slightly different moment in the same empty
    interval. A jitter null tests TEMPORAL SPECIFICITY: a unit merely more active
    throughout the empty period cannot pass it. Because the displaced window overlaps the
    true one by at least 331 ms, the test is conservative.

CLASSES  (all units, any quality; two-sided test, direction from the sign of the effect)
    O+   rate in the omitted slot above the jitter null, q <= 0.01
    O-   rate below the jitter null, q <= 0.01
    O++  an O+ unit that also ramps: significant positive linear trend across the slot,
         tested against the same jitter null

    The previous pipeline was one-sided and could not detect suppression: 3,457 of 6,655
    units have a negative omission-versus-delay effect and none reaches p = 0.05 there.
    O- has therefore never been measurable on this corpus.

ONSET LATENCY
    A shift-shuffle null preserves each trial's autocorrelation by circularly rotating the
    trial's spike train within the analysis epoch, so slow structure survives and only the
    time-locking to the omission is destroyed. At each time bin the observed across-trial
    mean is compared with that null, and onset is the first bin beginning a run of
    MIN_RUN consecutive significant bins.

    Onset is searched only at t >= 0. Before the omitted stimulus fails to appear, the
    animal cannot know the trial is an omission trial, so a pre-zero onset would indicate
    leakage from the preceding delay rather than an omission response, and is reported as
    a diagnostic rather than accepted as a latency.

OUTPUT
    outputs/classification/omission_jitter_units.csv       one row per unit
    outputs/classification/omission_jitter_by_area.csv     counts and prevalence per area
    outputs/classification/omission_jitter_by_area_animal.csv
    outputs/classification/omission_jitter_by_session.csv
    outputs/classification/omission_onset_latency.csv      per unit, and per area summary
    outputs/classification/omission_jitter_receipt.json
"""
from __future__ import annotations

import argparse
import json
import zlib
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats as sst

# _P (jnwb.paths) used to be imported after this insert referenced it -- NameError. Same bug
# already fixed in classify_omission_units_grand.py 2026-08-11; applied here 2026-08-14 while
# fixing this file's bh() divisor bug, since it blocked running the script to verify that fix.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import omission as oa
from omission.jnwb_ext.unit_classification import (EPOCH_ONSETS_MS, PRESENTATION_DUR_MS,
                                      omission_events, precompute_condition_onsets)
from jnwb import paths as _P
from jnwb.statistics import clopper_pearson

NWB_DIR = _P.nwb_dir()
OUT_DIR = _P.REPO_ROOT / "outputs/classification"

JITTER_MS = 200.0
N_SHUFFLES = 1000
ALPHA = 0.01
N_RAMP_BINS = 6
MIN_OMISSION_TRIALS = 8
POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}

# onset search
ONSET_BIN_MS = 20.0
ONSET_LO_MS, ONSET_HI_MS = -400.0, 1000.0
MIN_RUN = 3               # consecutive significant bins to declare an onset
ONSET_ALPHA = 0.05


def bh(p):
    """Benjamini-Hochberg FDR, delegating to jnwb.StatisticalAnalysis.fdr_correct (scipy
    false_discovery_control). Was a local re-implementation with a backwards rank divisor
    (np.arange(n, 0, -1) instead of np.arange(1, n+1)) that silently under-corrected every
    q-value in this file's output until fixed 2026-08-14 -- see
    artifacts/.lab/bh-fdr-backwards-divisor-fix-20260814.json."""
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    q = np.full(p.shape, np.nan)
    v = p[ok]
    if v.size == 0:
        return q
    q[ok] = oa.StatisticalAnalysis.fdr_correct(v)
    return q


def counts_in(st, t0):
    """Vectorised spike counts in [t0, t0+dur) for any shaped array of onsets."""
    dur = PRESENTATION_DUR_MS / 1000.0
    a = np.searchsorted(st, t0.ravel(), "left")
    b = np.searchsorted(st, (t0 + dur).ravel(), "right")
    return (b - a).reshape(t0.shape).astype(float)


def binned(st, t0, edges_rel):
    """Counts per bin for every onset in t0. Returns (…, nbins)."""
    e = t0[..., None] + edges_rel[None, ...] if t0.ndim == 1 else t0[..., None] + edges_rel
    idx = np.searchsorted(st, e.ravel()).reshape(e.shape)
    return np.diff(idx, axis=-1).astype(float)


def slopes_from_bins(c, centres):
    """Least-squares slope per row of binned counts."""
    x = centres - centres.mean()
    denom = (x ** 2).sum()
    return (c - c.mean(axis=-1, keepdims=True)) @ x / denom if denom > 0 else np.zeros(c.shape[:-1])


def analyse_session(nwb_path, rng, do_onset=True):
    sess = oa.read(str(nwb_path))
    onsets = precompute_condition_onsets(sess, correct_only=True)
    try:
        udf = sess.get_units()
    except Exception:
        udf = getattr(sess, "units", None)
    if udf is None or len(udf) == 0:
        return [], []

    om = []
    for cond, slot in omission_events():
        arr = onsets.get(cond)
        if arr is None or len(arr) == 0:
            continue
        om.append(np.asarray(arr, float) + EPOCH_ONSETS_MS[f"p{slot}"] / 1000.0)
    if not om:
        return [], []
    om = np.concatenate(om)
    if om.size < MIN_OMISSION_TRIALS:
        return [], []

    dur = PRESENTATION_DUR_MS / 1000.0
    jit = JITTER_MS / 1000.0
    D = rng.uniform(-jit, jit, size=(N_SHUFFLES, om.size))
    shifted = om[None, :] + D                                   # (S, T)

    ramp_edges = np.linspace(0.0, dur, N_RAMP_BINS + 1)
    ramp_centres = (ramp_edges[:-1] + ramp_edges[1:]) / 2.0

    obs_edges = om[:, None] + ramp_edges[None, :]               # (T, B+1)
    n_on = int(np.ceil((ONSET_HI_MS - ONSET_LO_MS) / ONSET_BIN_MS))
    on_edges_rel = (ONSET_LO_MS + np.arange(n_on + 1) * ONSET_BIN_MS) / 1000.0
    on_centres = (on_edges_rel[:-1] + on_edges_rel[1:]) / 2.0 * 1000.0
    epoch_len = on_edges_rel[-1] - on_edges_rel[0]

    stem = os.path.basename(nwb_path).replace("_rec.nwb", "").replace(".nwb", "")
    rows, onset_rows = [], []

    for ridx in range(len(udf)):
        try:
            st = np.sort(np.asarray(sess.get_spike_times(ridx), float))
        except Exception:
            continue
        if st.size < 2:
            continue
        meta = udf.iloc[ridx]

        # ---- rate against the jitter null -------------------------------------
        obs = counts_in(st, om).mean() / dur
        null = counts_in(st, shifted).mean(axis=1) / dur
        centre = float(null.mean())
        eff = float(obs - centre)
        p_rate = (1.0 + np.sum(np.abs(null - centre) >= abs(eff))) / (N_SHUFFLES + 1.0)

        # ---- ramp against the same null ---------------------------------------
        c_obs = np.diff(np.searchsorted(st, obs_edges.ravel()).reshape(obs_edges.shape),
                        axis=-1).astype(float)
        s_obs = float(slopes_from_bins(c_obs, ramp_centres).mean())
        sh_edges = shifted[..., None] + ramp_edges
        c_sh = np.diff(np.searchsorted(st, sh_edges.ravel()).reshape(sh_edges.shape),
                       axis=-1).astype(float)
        s_null = slopes_from_bins(c_sh, ramp_centres).mean(axis=1)
        cs = float(s_null.mean())
        eff_s = s_obs - cs
        p_ramp = (1.0 + np.sum(np.abs(s_null - cs) >= abs(eff_s))) / (N_SHUFFLES + 1.0)

        rows.append({
            "session": stem, "unit_row": ridx,
            "unit_id": meta.get("unit_id", ridx), "area": meta.get("area"),
            "quality": meta.get("quality"), "firing_rate": meta.get("firing_rate"),
            "n_omission_trials": int(om.size),
            "rate_omission_hz": float(obs), "rate_jitter_null_hz": centre,
            "effect_hz": eff, "p_rate": float(p_rate),
            "slope_omission_hz_s": s_obs, "slope_null_hz_s": cs,
            "slope_effect": float(eff_s), "p_ramp": float(p_ramp),
        })

        # ---- onset latency, shift-shuffle null --------------------------------
        if not do_onset:
            continue
        obs_bins = binned(st, om + on_edges_rel[0], on_edges_rel - on_edges_rel[0])
        obs_psth = obs_bins.mean(axis=0)
        rot = rng.integers(0, n_on, size=(N_SHUFFLES, om.size))
        nullm = np.empty((N_SHUFFLES, n_on))
        for s in range(N_SHUFFLES):
            # circular rotation of each trial's binned train preserves autocorrelation
            r = rot[s]
            idx = (np.arange(n_on)[None, :] + r[:, None]) % n_on
            nullm[s] = np.take_along_axis(obs_bins, idx, axis=1).mean(axis=0)
        mu, sd = nullm.mean(axis=0), nullm.std(axis=0, ddof=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            pb = 2 * (1 - sst.norm.cdf(np.abs(obs_psth - mu) / np.where(sd > 0, sd, np.nan)))
        sig = np.isfinite(pb) & (pb <= ONSET_ALPHA)
        post = on_centres >= 0
        onset = np.nan
        for i in range(n_on - MIN_RUN + 1):
            if post[i] and sig[i:i + MIN_RUN].all():
                onset = float(on_centres[i])
                break
        pre_leak = bool(any(sig[i:i + MIN_RUN].all()
                            for i in range(n_on - MIN_RUN + 1) if on_centres[i] < 0))
        onset_rows.append({
            "session": stem, "unit_row": ridx, "unit_id": meta.get("unit_id", ridx),
            "area": meta.get("area"), "onset_ms": onset,
            "pre_omission_significance": pre_leak,
            "n_sig_bins_post": int(sig[post].sum()),
        })
    return rows, onset_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sessions", default=None)
    ap.add_argument("--no-onset", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    BASE_SEED = 42

    files = sorted(f for f in os.listdir(NWB_DIR) if f.endswith(".nwb"))
    if args.sessions:
        want = [s.strip() for s in args.sessions.split(",")]
        files = [f for f in files if any(w in f for w in want)]
    if args.limit:
        files = files[: args.limit]

    t0 = time.time()
    allrows, allonsets, failed = [], [], []
    for i, f in enumerate(files, 1):
        try:
            # 2026-08-15 fix: was a single rng = np.random.default_rng(42) shared across the
            # whole sorted-file loop, consumed sequentially per unit inside analyse_session.
            # That made every session's jitter-null draws depend on which OTHER sessions ran
            # before it and in what order -- inserting the 22nd session (sub-V198o_ses-230629,
            # sorts before the 4 pre-existing V198o sessions) silently shifted the RNG draw
            # stream for every session processed after that point, producing raw-value changes
            # (rate_omission_hz, p_rate, slope_effect, etc.) for UNCHANGED sessions between the
            # pre-2026-08-11-corpus-addition run and later runs -- documented as an unresolved,
            # not-purely-BH-fix-attributable discrepancy in
            # artifacts/.lab/bh-fdr-backwards-divisor-fix-20260814.json. Root cause, not a BH
            # issue: fixed by seeding each session's own RNG from a stable hash of its filename
            # (zlib.crc32, NOT Python's hash() -- hash() on a str is randomized per-interpreter-
            # run via PYTHONHASHSEED, which would not even be reproducible run-to-run), combined
            # with BASE_SEED via numpy's SeedSequence-spawning form of default_rng. Every
            # session's result is now independent of corpus membership/order/size by
            # construction, not just by convention.
            rng = np.random.default_rng((BASE_SEED, zlib.crc32(f.encode())))
            r, o = analyse_session(os.path.join(NWB_DIR, f), rng, not args.no_onset)
            allrows += r
            allonsets += o
            print(f"[{datetime.now():%H:%M:%S}] {i}/{len(files)} {f}: {len(r)} units "
                  f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            failed.append({"file": f, "error": f"{type(e).__name__}: {e}"})
            print(f"[{datetime.now():%H:%M:%S}] {i}/{len(files)} {f}: FAILED {e}", flush=True)

    df = pd.DataFrame(allrows)
    if df.empty:
        print("no units analysed")
        return
    df["q_rate"] = bh(df.p_rate.values)
    df["q_ramp"] = bh(df.p_ramp.values)
    df["area10"] = df.area.replace(POOL)
    df["animal"] = df.session.str.split("_").str[0].str.replace("sub-", "", regex=False)
    df["is_o_plus"] = (df.q_rate <= ALPHA) & (df.effect_hz > 0)
    df["is_o_minus"] = (df.q_rate <= ALPHA) & (df.effect_hz < 0)
    df["is_o_plusplus"] = df.is_o_plus & (df.q_ramp <= ALPHA) & (df.slope_effect > 0)
    df["omission_class"] = np.where(df.is_o_plusplus, "O++",
                             np.where(df.is_o_plus, "O+",
                             np.where(df.is_o_minus, "O-", "ns")))
    df.to_csv(os.path.join(OUT_DIR, "omission_jitter_units.csv"), index=False)

    def tab(keys, name):
        rows = []
        for k, g in df.groupby(keys):
            n = len(g)
            rec = dict(zip(keys if isinstance(keys, list) else [keys],
                           k if isinstance(k, tuple) else (k,)))
            rec["screened"] = n
            for cls, m in [("O++", g.is_o_plusplus), ("O+", g.is_o_plus),
                           ("O-", g.is_o_minus)]:
                kk = int(m.sum())
                lo, hi = clopper_pearson(kk, n)
                rec[cls] = kk
                rec[f"{cls}_%"] = round(100 * kk / n, 2)
                rec[f"{cls}_ci95"] = f"{100*lo:.2f}-{100*hi:.2f}"
            rows.append(rec)
        t = pd.DataFrame(rows)
        t.to_csv(os.path.join(OUT_DIR, name), index=False)
        return t

    by_area = tab(["area10"], "omission_jitter_by_area.csv")
    tab(["area10", "animal"], "omission_jitter_by_area_animal.csv")
    tab(["session"], "omission_jitter_by_session.csv")

    on = pd.DataFrame(allonsets)
    if len(on):
        on["area10"] = on.area.replace(POOL)
        on = on.merge(df[["session", "unit_row", "omission_class"]],
                      on=["session", "unit_row"], how="left")
        on.to_csv(os.path.join(OUT_DIR, "omission_onset_latency.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "rate_null": f"temporal jitter, window displaced by D ~ U(-{JITTER_MS:g}, +{JITTER_MS:g}) ms",
        "onset_null": "shift-shuffle: each trial's binned train circularly rotated, which "
                      "preserves its autocorrelation and destroys only time-locking",
        "window_ms": [0, PRESENTATION_DUR_MS], "n_shuffles": N_SHUFFLES, "seed": 42,
        "two_sided": True, "alpha_fdr": ALPHA,
        "onset": {"bin_ms": ONSET_BIN_MS, "search_ms": [ONSET_LO_MS, ONSET_HI_MS],
                  "min_run_bins": MIN_RUN, "alpha": ONSET_ALPHA,
                  "constraint": "onset accepted only at t >= 0; the animal cannot know a "
                                "trial is an omission trial before the stimulus fails to "
                                "appear, so earlier significance is reported as "
                                "pre_omission_significance rather than as a latency"},
        "n_sessions_ok": len(files) - len(failed), "n_sessions_failed": len(failed),
        "failures": failed[:20], "n_units": int(len(df)),
        "counts": {k: int(v) for k, v in df.omission_class.value_counts().items()},
        "n_sessions_contributing_o_plus": int(df[df.is_o_plus].session.nunique()),
        "n_units_with_onset": int(on.onset_ms.notna().sum()) if len(on) else 0,
        "median_onset_ms": float(on.onset_ms.median()) if len(on) and
                           on.onset_ms.notna().any() else None,
        "n_pre_omission_significant": int(on.pre_omission_significance.sum()) if len(on) else 0,
        "outputs": ["omission_jitter_units.csv", "omission_jitter_by_area.csv",
                    "omission_jitter_by_area_animal.csv", "omission_jitter_by_session.csv",
                    "omission_onset_latency.csv"],
        "runtime_s": round(time.time() - t0, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__},
    }
    json.dump(receipt, open(os.path.join(OUT_DIR, "omission_jitter_receipt.json"), "w",
                            encoding="utf-8"), indent=2)
    print(f"\nunits {len(df):,} | " +
          " ".join(f"{k}={v}" for k, v in df.omission_class.value_counts().items()))
    print(f"O+ from {receipt['n_sessions_contributing_o_plus']} sessions | "
          f"onsets {receipt['n_units_with_onset']} | runtime {receipt['runtime_s']}s")
    print(by_area.to_string(index=False))


if __name__ == "__main__":
    main()
