r"""
Per-area, per-band: does omission (RXRR, p2 omitted) damp band power relative to that
channel's own baseline, and if so, when does the dampening reliably begin -- relative to
when the SAME area, SAME slot, would show a real-stimulus response (RRRR, p2 real)?

TWO QUESTIONS
    1. MAGNITUDE (-> barplot). Per area x band: mean session-level dB re baseline in the p2
       window (1031-1562 ms from p1, RXRR), one-sample test against zero (paired_location
       with b=0, i.e. Wilcoxon signed-rank or paired t chosen by Shapiro-Wilk on the session
       values, same convention condition_p2_band_stats already uses elsewhere in this repo),
       one-sided ("less" -- is power BELOW baseline). Family = all area x band cells (up to
       50: 10 areas x 5 bands), Holm and BH both reported (figstats.correct).
    2. ONSET LATENCY (-> per-area comparison). Per area x band: cluster-based sign-flip
       permutation test (Maris & Oostenveld one-sample cluster test) on the PAIRED, WITHIN-
       SESSION DIFFERENCE curve dB_RXRR(t) - dB_RRRR(t) (one-sided, difference < 0 -- omission
       trace running below the real-stimulus trace), restricted to the p2-to-p3 window.
       Bootstrap CI over sessions (resample with replacement), same method
       aggregate_omission_onset_clusters.py already established for the (unrelated)
       decode-accuracy onset question -- reused here, not reinvented.

       REDESIGNED 2026-08-15 from an earlier version that ran two INDEPENDENT one-sample tests
       (RXRR vs its own baseline, RRRR vs its own baseline) and compared their onsets post hoc.
       That version found a near-instantaneous ( ~9 ms post p2-onset) "onset" in nearly every
       area x band cell, for BOTH conditions simultaneously -- physiologically implausible for
       theta (125-250 ms cycle) and traced to a shared pre-p2 ramp/drift common to both
       conditions (they are physically identical trials up to p2 onset) riding through the
       search-window boundary, likely compounded by TFR time-frequency smearing (see
       omission-signal skill Sec.4). The paired-difference design cancels that shared component
       structurally, not just via a post-hoc flag; see paired_diff_traces() docstring.

DATA SOURCE
    outputs/condition_tfr_maps_p1d1p2d2p3_v2/maps.npz -- the current canonical condition-map
    extraction per context/PROJECT_STATE.md (2026-08-14); see fig04xx_3d_condition_tfr.py's
    docstring for why v2, not the D:-path-broken/superseded v1 the main fig04 script still
    points at. Values are per-session RATIO (power / that channel's own middle-of-d1 baseline),
    already averaged over channels and trials within a session; log is taken once here, after
    averaging the band's frequency rows and, for the onset test, per session (never across
    sessions in ratio space at this stage -- see band_ratio_db below).

CAUSALITY
    An omission cannot be detected before the brain could have processed that SOMETHING was (or
    was not) at that slot. Two guarantees, not one:
      (a) structural -- the onset test operates on dB_RXRR(t) - dB_RRRR(t), and RXRR/RRRR are
          the SAME physical trial content up to p2 onset (the animal cannot know which condition
          it is in before the slot resolves), so this difference is identically zero in
          expectation before that point regardless of any shared ramp/drift; a real, non-noise
          divergence cannot exist before p2 onset by construction, not merely by convention.
      (b) search-window -- the cluster search is additionally restricted to bins >= p2 onset
          (1031 ms) and < p3 onset (2062 ms), the same restriction
          aggregate_omission_onset_clusters.py applies to its own (different) onset question,
          for the same reason: a bin before the slot begins cannot carry information about what
          happened AT that slot.
    The RRRR-alone real-stimulus response onset is still computed and reported
    (stim_response_onset_ms) but is now DIAGNOSTIC ONLY, not a causality gate -- see the
    ONSET LATENCY section below for why the earlier post-hoc-comparison design was replaced.

OUTPUT
    outputs/classification/omission_band_dampening_magnitude.csv   (area x band magnitude test)
    outputs/classification/omission_band_dampening_onset.csv       (area x band onset latency,
                                                                     RXRR and RRRR, causality flag)
    artifacts/data/omission_band_dampening_onset_detail.json       (curves, clusters, receipt)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sst

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))

from jnwb import paths as _P                              # noqa: E402
from omission.jnwb_ext.spectral import to_db                            # noqa: E402
from figstats import Result, correct, paired_location, write  # noqa: E402
from figstyle import EPOCH_ONSETS_MS, AREA_ORDER            # noqa: E402

MAPS_NPZ = str(_P.outputs_dir() / "condition_tfr_maps_p1d1p2d2p3_v2" / "maps.npz")
OUT_DIR = REPO_ROOT / "outputs" / "classification"
DETAIL_JSON = REPO_ROOT / "artifacts" / "data" / "omission_band_dampening_onset_detail.json"

BANDS = {"theta": (4, 8), "alpha": (8, 14), "beta": (14, 30),
         "low_gamma": (30, 50), "high_gamma": (50, 80)}

P2_ONSET_MS = EPOCH_ONSETS_MS["p2"]      # 1031 -- the omitted/real slot's own onset
P3_ONSET_MS = EPOCH_ONSETS_MS["p3"]      # 2062 -- next real slot; search window's right edge
P2_WINDOW_MS = (P2_ONSET_MS, EPOCH_ONSETS_MS["d2"])   # 1031-1562, the magnitude test's window

MIN_SESSIONS_FOR_CLUSTER_TEST = 3   # below this, report descriptive-only (matches project's own
                                     # FST "illustrative, not a population estimate" convention)
N_PERM = 500
N_BOOT = 2000
BOOT_SEED = 42


def load_condition_maps():
    z = np.load(MAPS_NPZ, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            maps[k] = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
    return maps, freqs, times


def area_cond_sessions(maps, area, cond, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer and k.split("|")[3] == cond}


def band_ratio_trace(m, freqs, lo, hi):
    sel = (freqs >= lo) & (freqs < hi)
    return np.nanmean(m[sel], axis=0) if sel.any() else np.full(m.shape[1], np.nan)


def session_db_traces(sess, freqs, lo, hi):
    """dict session -> dB(t), one array per session -- ratio (not yet logged) per session,
    THEN log once per session (never pooled across sessions in ratio space here; the group
    curve used by the cluster test is the mean of these already-per-session dB traces, i.e.
    log-then-average across sessions, which is a deliberately different, more conservative
    order than the "average ratio across sessions, then log once" convention used for a single
    grand-mean spectrogram -- appropriate here because the group-level statistic for a
    session-level cluster test must be built FROM independent per-session values, not from a
    single pooled curve that no longer carries per-session variance)."""
    return {s: to_db(band_ratio_trace(m, freqs, lo, hi)) for s, m in sess.items()}


def paired_diff_traces(sess_rxrr, sess_rrrr, freqs, lo, hi):
    """dict session -> (dB_RXRR(t) - dB_RRRR(t)), restricted to sessions with BOTH conditions.

    RXRR and RRRR are physically identical trials up to p2 onset (the animal cannot know which
    condition it is in before that point), so any shared pre-p2 ramp or anticipatory drift is
    common to both and cancels in the subtraction -- this isolates the OMISSION-SPECIFIC
    divergence rather than each condition's raw deviation from its own baseline. First design
    (independent one-sample tests of RXRR<baseline and RRRR>baseline, compared post hoc) found
    a spurious near-instantaneous ( ~9 ms post p2-onset) "onset" in nearly every area x band
    cell, for BOTH conditions -- diagnosed as a shared pre-p2 trend riding through the boundary
    (consistent with TFR spectral/temporal smearing, omission-signal skill Sec.4) rather than a
    genuine fast neural response; this paired design is the fix, not a cosmetic change.
    """
    common = sorted(set(sess_rxrr) & set(sess_rrrr))
    out = {}
    for s in common:
        a = to_db(band_ratio_trace(sess_rxrr[s], freqs, lo, hi))
        b = to_db(band_ratio_trace(sess_rrrr[s], freqs, lo, hi))
        out[s] = a - b
    return out


def magnitude_test(area, band, lo, hi, sess_rxrr, freqs, times):
    tmask = (times >= P2_WINDOW_MS[0]) & (times < P2_WINDOW_MS[1])
    vals = []
    for s, m in sess_rxrr.items():
        r = band_ratio_trace(m, freqs, lo, hi)[tmask]
        if np.any(np.isfinite(r)):
            vals.append(to_db(np.nanmean(r)))
    vals = np.array(vals, float)
    zeros = np.zeros_like(vals)
    res = paired_location(
        zeros, vals,  # 0 - dB: positive means dB < 0 (dampened) -- "less" tail below reads a-b
        figure="omission_band_dampening", panel="magnitude",
        question=f"{area} {band}: RXRR p2-window dB below zero?",
        unit="session", family="omission_band_dampening_magnitude", tail="greater",
        note=f"n={len(vals)} sessions; a - b = 0 - dB, tail='greater' so p answers "
             "'is dB reliably < 0'")
    return res, vals


def sign_flip_cluster_test(t_rel, curve_by_session, tail, valid_mask, n_perm=N_PERM, seed=BOOT_SEED):
    """One-sample cluster-based permutation test (Maris & Oostenveld sign-flip), on the mean
    across sessions of each session's own dB(t) curve. tail='less' tests dB<0 (dampening),
    'greater' tests dB>0 (real-stimulus response). Search restricted to valid_mask (causality:
    bins before the slot's own onset are excluded before the cluster search ever runs, not
    filtered after -- see module docstring).
    """
    sessions = sorted(curve_by_session)
    X = np.stack([curve_by_session[s] for s in sessions], axis=0)   # (n_sessions, n_bins)
    X = X[:, valid_mask]
    t_rel_v = t_rel[valid_mask]
    n_sessions, n_bins = X.shape
    sign = -1.0 if tail == "less" else 1.0
    stat_obs = sign * np.nanmean(X, axis=0)          # positive = "in the hypothesized direction"

    rng = np.random.default_rng(seed)
    null_stats = np.empty((n_perm, n_bins))
    for p in range(n_perm):
        flips = rng.choice([-1.0, 1.0], size=n_sessions)
        null_stats[p] = sign * np.nanmean(X * flips[:, None], axis=0)

    per_bin_threshold = np.nanpercentile(null_stats, 95, axis=0)

    def clusters_above(curve, threshold):
        above = curve > threshold
        out, i, n = [], 0, len(curve)
        while i < n:
            if above[i]:
                j = i
                while j < n and above[j]:
                    j += 1
                out.append((i, j, float(np.nansum(curve[i:j] - threshold[i:j]))))
                i = j
            else:
                i += 1
        return out

    obs_clusters = clusters_above(stat_obs, per_bin_threshold)
    null_max_mass = np.array([
        max((c[2] for c in clusters_above(null_stats[p], per_bin_threshold)), default=0.0)
        for p in range(n_perm)
    ])

    sig_clusters = []
    for (i, j, mass) in obs_clusters:
        p_val = float(np.mean(null_max_mass >= mass))
        sig_clusters.append({"start_ms": float(t_rel_v[i]), "end_ms": float(t_rel_v[j - 1]),
                             "mass": mass, "p_cluster": p_val, "significant": bool(p_val < 0.05)})
    onset_ms = next((c["start_ms"] for c in sig_clusters if c["significant"]), None)
    return {"onset_ms": onset_ms, "clusters": sig_clusters, "n_sessions": n_sessions,
            "t_rel_ms": t_rel_v.tolist(), "stat_obs": stat_obs.tolist(),
            "null_max_mass_95pct": float(np.nanpercentile(null_max_mass, 95))}


def bootstrap_onset_ci(t_rel, curve_by_session, tail, valid_mask, n_boot=N_BOOT, seed=BOOT_SEED):
    sessions = sorted(curve_by_session)
    n = len(sessions)
    if n < MIN_SESSIONS_FOR_CLUSTER_TEST:
        return None
    rng = np.random.default_rng(seed)
    onsets = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        resampled = {f"{sessions[i]}__{k}": curve_by_session[sessions[i]] for k, i in enumerate(idx)}
        result = sign_flip_cluster_test(t_rel, resampled, tail, valid_mask, n_perm=100, seed=int(rng.integers(0, 2**31)))
        if result["onset_ms"] is not None:
            onsets.append(result["onset_ms"])
    if not onsets:
        return {"n_boot_with_onset": 0, "n_boot": n_boot, "ci_lo_ms": None, "ci_hi_ms": None, "median_ms": None}
    onsets = np.array(onsets)
    return {"n_boot_with_onset": int(len(onsets)), "n_boot": n_boot,
            "ci_lo_ms": float(np.percentile(onsets, 2.5)), "ci_hi_ms": float(np.percentile(onsets, 97.5)),
            "median_ms": float(np.median(onsets))}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DETAIL_JSON.parent.mkdir(parents=True, exist_ok=True)
    maps, freqs, times = load_condition_maps()
    valid_mask = (times >= P2_ONSET_MS) & (times < P3_ONSET_MS)
    t_rel = times  # already p1-relative; "onset_ms" values below are p1-relative, not p2-relative

    mag_results = []
    mag_extra = []   # parallel list, same append order as mag_results -- see note below
    onset_rows = []
    detail = {}

    for area in AREA_ORDER:
        for band, (lo, hi) in BANDS.items():
            sess_rxrr = area_cond_sessions(maps, area, "RXRR")
            sess_rrrr = area_cond_sessions(maps, area, "RRRR")
            if not sess_rxrr:
                continue

            res, vals = magnitude_test(area, band, lo, hi, sess_rxrr, freqs, times)
            mag_results.append(res)
            # Result.effect is a STANDARDIZED effect size (Cohen's dz for the t-test branch,
            # rank-biserial r for Wilcoxon) -- not the dB magnitude a barplot needs. Carry the
            # actual mean dB separately, in the same append order as mag_results, so it can be
            # zipped back on after figstats.correct() (which sets p_holm/q_bh in place and does
            # not reorder the list).
            mag_extra.append({"area": area, "band": band,
                              "mean_db": float(np.nanmean(vals)) if vals.size else np.nan,
                              "median_db": float(np.nanmedian(vals)) if vals.size else np.nan,
                              "n_sessions_magnitude": int(vals.size)})

            curves_diff = paired_diff_traces(sess_rxrr, sess_rrrr, freqs, lo, hi)
            n_sess = len(curves_diff)
            # diagnostic-only, not used for the onset/causality decision (see paired_diff_traces
            # docstring for why the paired design makes this comparison structurally moot)
            curves_rrrr = session_db_traces(sess_rrrr, freqs, lo, hi)

            row = {"area": area, "band": band, "n_sessions": n_sess,
                  "mean_p2window_db": float(np.nanmean(vals)) if vals.size else np.nan}

            if n_sess < MIN_SESSIONS_FOR_CLUSTER_TEST:
                row.update({"omission_onset_ms": None, "omission_onset_ci_lo_ms": None,
                           "omission_onset_ci_hi_ms": None, "stim_response_onset_ms": None,
                           "note": f"n={n_sess} sessions, below MIN_SESSIONS_FOR_CLUSTER_TEST="
                                  f"{MIN_SESSIONS_FOR_CLUSTER_TEST} -- descriptive only, no "
                                  "cluster test run"})
                onset_rows.append(row)
                continue

            damp = sign_flip_cluster_test(t_rel, curves_diff, "less", valid_mask)
            damp_boot = bootstrap_onset_ci(t_rel, curves_diff, "less", valid_mask)
            resp = sign_flip_cluster_test(t_rel, curves_rrrr, "greater", valid_mask)

            row.update({
                "omission_onset_ms": damp["onset_ms"],
                "omission_onset_ci_lo_ms": damp_boot["ci_lo_ms"] if damp_boot else None,
                "omission_onset_ci_hi_ms": damp_boot["ci_hi_ms"] if damp_boot else None,
                "stim_response_onset_ms": resp["onset_ms"],
                "note": "",
            })
            onset_rows.append(row)
            detail[f"{area}|{band}"] = {"paired_diff_dampening": damp,
                                        "paired_diff_dampening_boot": damp_boot,
                                        "stim_response_diagnostic_only": resp,
                                        "n_sessions_paired": n_sess,
                                        "n_sessions_rrrr": len(curves_rrrr)}
            print(f"{area} {band}: n={n_sess} paired_diff_onset={damp['onset_ms']} "
                 f"(diagnostic stim_response_onset={resp['onset_ms']})")

    mag_results = correct(mag_results)
    assert len(mag_results) == len(mag_extra)
    mag_df = pd.DataFrame([{
        "area": e["area"], "band": e["band"], "mean_db": e["mean_db"],
        "median_db": e["median_db"], "n_sessions": e["n_sessions_magnitude"],
        "test": r.test, "effect_name": r.effect_name, "standardized_effect": r.effect,
        "p": r.p, "p_holm": r.p_holm, "q_bh": r.q_bh, "tail": r.tail, "note": r.note,
    } for r, e in zip(mag_results, mag_extra)])
    mag_df.to_csv(OUT_DIR / "omission_band_dampening_magnitude.csv", index=False)
    print("wrote", OUT_DIR / "omission_band_dampening_magnitude.csv")

    onset_df = pd.DataFrame(onset_rows)
    onset_df.to_csv(OUT_DIR / "omission_band_dampening_onset.csv", index=False)
    print("wrote", OUT_DIR / "omission_band_dampening_onset.csv")

    DETAIL_JSON.write_text(json.dumps({
        "method_magnitude": "paired_location(0, dB) tail='greater' == one-sample test of "
                            "dB<0, Wilcoxon signed-rank or paired t chosen by Shapiro-Wilk, "
                            "unit=session, window=p2 (1031-1562 ms); family = all area x band "
                            "cells, Holm and BH both reported",
        "method_onset": "cluster-based sign-flip permutation (Maris & Oostenveld) on the PAIRED "
                        "within-session difference dB_RXRR(t)-dB_RRRR(t), one-sided (<0), "
                        f"n_perm={N_PERM}, per-bin null 95th-pct threshold, cluster mass vs "
                        "null max-cluster-mass distribution; bootstrap CI over sessions "
                        f"(n_boot={N_BOOT}); search restricted to p2-onset..p3-onset "
                        f"({P2_ONSET_MS}-{P3_ONSET_MS} ms). REDESIGNED 2026-08-15 from two "
                        "independent one-sample tests (see module docstring) after that design "
                        "produced implausible near-instantaneous onsets from a shared pre-p2 "
                        "trend common to both conditions.",
        "causality_check": "structural: RXRR and RRRR are the same trial content up to p2 "
                           "onset, so the paired difference is zero in expectation before that "
                           "point regardless of any shared drift; stim_response_onset_ms "
                           "(RRRR-alone cluster test) is retained as a diagnostic column only, "
                           "not a causality gate",
        "bands_hz": BANDS, "p2_window_ms": list(P2_WINDOW_MS),
        "min_sessions_for_cluster_test": MIN_SESSIONS_FOR_CLUSTER_TEST,
        "source": MAPS_NPZ, "detail": detail,
    }, indent=2), encoding="utf-8")
    print("wrote", DETAIL_JSON)


if __name__ == "__main__":
    main()
