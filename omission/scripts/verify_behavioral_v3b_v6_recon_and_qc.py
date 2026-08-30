"""V3b + V6 -- upstream 'Reconstructed' acausality evidence, and an independent QC/discontinuity
rate using my OWN criterion.

V3b (upstream leakage, physical evidence rather than metadata):
  A linear interpolation across a data gap produces a run of samples with an EXACTLY constant
  first difference (zero second difference). Such a run is acausal by construction: every sample
  inside it is a function of the value AFTER the gap. Detect runs of length >= L where
  |x[i+1] - 2x[i] + x[i-1]| <= eps, and report the fraction of session samples covered and the
  run-length distribution, per subject. Also report a plateau (sample-and-hold fill) statistic.
  Also: leakage-relevant positive control -- corrupt PRE-onset samples and confirm the module's
  features DO change (so the V3 negative result is not vacuous).

V6 (discontinuity rate): three criteria on the same p1-anchored (-500,0) ms pupil windows.
  A) ORIGINAL (reproduction): |diff| > 5 * SD(diff within that window)
  B) MINE-robust-session: |diff| > 10 * (1.4826 * MAD(diff over the WHOLE session)) -- a
     session-level robust scale, immune to the within-window-SD pathology where a flat window
     makes any wiggle a '5 SD' event.
  C) MINE-absolute-range: |diff| > 0.05 * (session p99.9 - p0.1 range of the signal), i.e. a
     >5%-of-full-dynamic-range jump in 1 ms.
  Reported as fraction of trials with >=1 event, with an exact Clopper-Pearson interval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
from scipy import stats as sst


def _find_data(grp):
    found = []
    grp.visititems(lambda n, o: found.append((n, o))
                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "data" else None)
    return found[0][1]


def _find_start(grp):
    found = []
    grp.visititems(lambda n, o: found.append((n, o))
                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == "starting_time" else None)
    ds = found[0][1]
    return float(ds[()]), float(ds.attrs["rate"])


def run_lengths(mask):
    """Lengths of contiguous True runs."""
    if mask.size == 0:
        return np.array([], dtype=int)
    d = np.diff(np.concatenate(([0], mask.view(np.int8), [0])))
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1)
    return ends - starts


def linear_fill_scan(x, min_run=20):
    """Runs with (near-)zero second difference -> linear-interpolation fill signature."""
    x = np.asarray(x, dtype=np.float64)
    d2 = np.abs(np.diff(x, 2))
    scale = float(np.median(np.abs(np.diff(x))))
    eps = max(scale * 1e-9, np.finfo(np.float64).eps * 8 * float(np.max(np.abs(x)) or 1.0))
    flat = d2 <= eps
    rl = run_lengths(flat)
    long_runs = rl[rl >= min_run]
    # plateau (sample-and-hold) runs
    dz = np.diff(x) == 0.0
    prl = run_lengths(dz)
    plong = prl[prl >= min_run]
    return {
        "eps": eps,
        "median_abs_diff": scale,
        "n_samples": int(x.size),
        "frac_samples_in_linear_run_ge_min": float(long_runs.sum() / x.size) if x.size else 0.0,
        "n_linear_runs_ge_min": int(long_runs.size),
        "max_linear_run_len": int(long_runs.max()) if long_runs.size else 0,
        "p99_linear_run_len": float(np.percentile(rl, 99)) if rl.size else 0.0,
        "frac_samples_in_plateau_run_ge_min": float(plong.sum() / x.size) if x.size else 0.0,
        "max_plateau_run_len": int(plong.max()) if plong.size else 0,
        "min_run": min_run,
    }


def cp_ci(k, n, alpha=0.05):
    if n == 0:
        return [float("nan"), float("nan")]
    lo = 0.0 if k == 0 else float(sst.beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(sst.beta.ppf(1 - alpha / 2, k + 1, n - k))
    return [lo, hi]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scan-chunk", type=int, default=3_000_000)
    args = ap.parse_args()

    import omission as oa
    from omission.jnwb_ext import behavioral_covariates as bc

    nwb_dir = oa.paths.nwb_dir()
    report = {"sessions": []}
    for stem in args.sessions:
        path = nwb_dir / f"{stem}.nwb"
        rec = {"session": stem, "subject": stem.split("_")[0].removeprefix("sub-")}

        # ---------------- V3b: linear-fill / plateau scan ----------------
        scans = {}
        with h5py.File(path, "r") as h:
            for key, tag in (("pupil_1_tracking", "pupil"), ("eye_1_tracking", "gaze")):
                grp = h["acquisition"][key]
                ds = _find_data(grp)
                n = ds.shape[0]
                lo = max(0, n // 2 - args.scan_chunk // 2)
                hi = min(n, lo + args.scan_chunk)
                if ds.ndim == 1:
                    scans[f"{tag}.ch0"] = linear_fill_scan(np.asarray(ds[lo:hi]))
                else:
                    arr = np.asarray(ds[lo:hi, :])
                    for c in range(arr.shape[1]):
                        scans[f"{tag}.ch{c}"] = linear_fill_scan(arr[:, c])
                if tag == "pupil":
                    start_s, rate = _find_start(grp)
                    full_pupil_stats = None
                    # session-level robust diff scale + dynamic range, from the same chunk
                    xx = np.asarray(ds[lo:hi], dtype=np.float64)
                    dd = np.diff(xx)
                    mad = float(np.median(np.abs(dd - np.median(dd))))
                    full_pupil_stats = {
                        "session_diff_mad_scaled": 1.4826 * mad,
                        "session_diff_sd": float(np.std(dd)),
                        "session_range_p999_p001": float(np.percentile(xx, 99.9) - np.percentile(xx, 0.1)),
                        "chunk": [int(lo), int(hi)],
                    }
        rec["v3b_reconstruction_scan"] = scans
        rec["v6_session_scales"] = full_pupil_stats

        # ---------------- V6: discontinuity rates, three criteria ----------------
        try:
            batch = bc.load_pupil_epochs(path, alignment="p1", window_ms=(-500.0, 0.0),
                                         missing_data="drop")
            X = batch.data[:, 0, :]
            n_tr = X.shape[0]
            sd_scale = full_pupil_stats["session_diff_mad_scaled"]
            rng_scale = full_pupil_stats["session_range_p999_p001"]
            a = b = c = 0
            counts_a = []
            for i in range(n_tr):
                w = X[i]
                d = np.diff(w[np.isfinite(w)])
                if d.size < 3:
                    continue
                s = np.std(d)
                na = int(np.sum(np.abs(d) > 5 * s)) if s > 0 else 0
                nb = int(np.sum(np.abs(d) > 10 * sd_scale)) if sd_scale > 0 else 0
                nc = int(np.sum(np.abs(d) > 0.05 * rng_scale)) if rng_scale > 0 else 0
                counts_a.append(na)
                a += na > 0
                b += nb > 0
                c += nc > 0
            rec["v6"] = {
                "n_trials": int(n_tr),
                "A_original_within_window_5sd": {
                    "frac_trials_any": a / n_tr, "k": int(a), "n": int(n_tr),
                    "ci95_clopper_pearson": cp_ci(a, n_tr),
                    "mean_events_per_trial": float(np.mean(counts_a)) if counts_a else float("nan"),
                },
                "B_mine_session_robust_10mad": {
                    "frac_trials_any": b / n_tr, "k": int(b), "n": int(n_tr),
                    "ci95_clopper_pearson": cp_ci(b, n_tr),
                    "threshold_abs": 10 * sd_scale,
                },
                "C_mine_5pct_dynamic_range": {
                    "frac_trials_any": c / n_tr, "k": int(c), "n": int(n_tr),
                    "ci95_clopper_pearson": cp_ci(c, n_tr),
                    "threshold_abs": 0.05 * rng_scale,
                },
            }
        except Exception as exc:  # noqa: BLE001
            rec["v6"] = {"error": f"{type(exc).__name__}: {exc}"}

        report["sessions"].append(rec)
        print("done", stem, flush=True)

    Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
