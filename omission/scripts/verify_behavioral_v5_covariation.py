"""V5 -- INDEPENDENT recomputation of pupil/gaze <-> neural pre-state covariation.

Deliberately different from the original receipt in implementation AND in statistic:

  * Behavioural features are recomputed HERE from raw h5py slabs (no behavioral_covariates
    import for the features themselves) -- but the module's own pupil mean is also extracted
    for a cross-check correlation, so a discrepancy in the module would be visible.
  * The neural pre-state is read on a STRICTLY (-500, 0) ms window (500 samples, last sample
    t = -1 ms). The original used (-500, +1) ms because load_analog_epochs demands a t=0
    sample; this version does its own slab reads and therefore never touches t >= 0.
  * PRIMARY statistic: blocked (contiguous 5-fold) cross-validated predictive R^2 of a neural
    pre-state quantity from the FULL behavioural feature vector (ridge, standardized).
    Contiguous blocks, not random folds, because trials inside a session drift slowly and
    random folds let a fold's neighbours leak into it. Random-fold R^2 is reported alongside
    so the size of that inflation is visible.
    r_effective = sqrt(max(R2, 0)) -- directly comparable to the r >~ 0.9 proxy-fidelity bar.
  * SECONDARY: per-pair Pearson-on-ranks with a CIRCULAR-SHIFT (block) permutation null, which
    respects within-session temporal autocorrelation; the original's asymptotic Spearman p
    does not.
  * Multiplicity: Benjamini-Hochberg over the whole family via jnwb StatisticalAnalysis.
  * Inferential unit = SESSION. Per-session estimates are summarised across sessions with a
    percentile bootstrap over sessions; nothing is pooled at trial level across sessions.
  * CEILING REFERENCE: the same blocked-CV R^2 for predicting one neural pre-state quantity
    from the OTHER neural pre-state quantities. This says how much shared, linearly-accessible
    pre-state structure exists at all, so behaviour's number can be read against something.
  * NEGATIVE CONTROL: the same pipeline with the behavioural design matrix circularly shifted
    by half the session, which destroys trial-wise correspondence but preserves autocorrelation.

Window: p1-anchored (-500, 0) ms, correct trials, all conditions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import stats as sst


# ---------------------------------------------------------------- raw readers (my own)

def _s(v):
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray) and v.shape == ():
        return _s(v.item())
    return v


def _num(group, name):
    v = group[name][:]
    if v.dtype.kind in "OSU":
        out = np.empty(v.shape[0], dtype=float)
        for i, x in enumerate(v):
            try:
                out[i] = float(_s(x))
            except (TypeError, ValueError):
                out[i] = np.nan
        return out
    return np.asarray(v, dtype=float)


def _find(grp, leaf):
    found = []
    grp.visititems(lambda n, o: found.append((n, o))
                   if isinstance(o, h5py.Dataset) and n.rsplit("/", 1)[-1] == leaf else None)
    found.sort(key=lambda t: (len(t[0].split("/")), t[0]))
    return found[0][1] if found else None


def trial_onsets(h, correct_only=True):
    iv = h["intervals/omission_glo_passive"]
    df = pd.DataFrame({c: _num(iv, c) for c in
                       ("start_time", "trial_num", "stimulus_number", "task_condition_number")})
    df["correct"] = _num(iv, "correct") if "correct" in iv else 1.0
    df = df[np.isclose(df["stimulus_number"], 2.0)]
    df = df[np.isfinite(df["start_time"]) & np.isfinite(df["trial_num"])]
    if correct_only:
        df = df[df["correct"] == 1.0]
    df = df.drop_duplicates("trial_num", keep="first").sort_values("start_time")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- statistics (my own)

def ols_slope(y):
    x = np.arange(y.size, dtype=float)
    xc = x - x.mean()
    return float(np.dot(xc, y - y.mean()) / np.dot(xc, xc))


def ridge_fit(Xtr, ytr, lam):
    Xm, Xs = Xtr.mean(0), Xtr.std(0)
    Xs[Xs == 0] = 1.0
    Z = (Xtr - Xm) / Xs
    ym = ytr.mean()
    A = Z.T @ Z + lam * np.eye(Z.shape[1])
    b = np.linalg.solve(A, Z.T @ (ytr - ym))
    return (Xm, Xs, ym, b)


def ridge_pred(model, X):
    Xm, Xs, ym, b = model
    return ((X - Xm) / Xs) @ b + ym


def cv_r2(X, y, n_folds=5, blocked=True, lam=1.0, seed=0):
    """Out-of-sample R^2 (1 - SSE/SST against the TRAIN mean, computed pooled over folds)."""
    n = y.size
    if n < 4 * n_folds:
        return float("nan")
    idx = np.arange(n)
    if blocked:
        folds = np.array_split(idx, n_folds)
    else:
        rng = np.random.default_rng(seed)
        perm = rng.permutation(idx)
        folds = np.array_split(perm, n_folds)
    pred = np.full(n, np.nan)
    base = np.full(n, np.nan)
    for f in folds:
        tr = np.setdiff1d(idx, f)
        m = ridge_fit(X[tr], y[tr], lam)
        pred[f] = ridge_pred(m, X[f])
        base[f] = y[tr].mean()
    sse = float(np.sum((y - pred) ** 2))
    sst_ = float(np.sum((y - base) ** 2))
    return 1.0 - sse / sst_ if sst_ > 0 else float("nan")


def rank_pearson(a, b):
    ra = sst.rankdata(a)
    rb = sst.rankdata(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def circshift_perm_p(a, b, n_perm=2000, seed=0):
    """Two-sided p for rank-Pearson under a circular-shift null (preserves autocorrelation)."""
    obs = abs(rank_pearson(a, b))
    n = a.size
    rng = np.random.default_rng(seed)
    shifts = rng.integers(max(1, n // 20), n - max(1, n // 20), size=n_perm)
    ra, rb = sst.rankdata(a), sst.rankdata(b)
    rb_c = rb - rb.mean()
    ra_c = ra - ra.mean()
    den = np.sqrt(np.sum(ra_c ** 2) * np.sum(rb_c ** 2))
    cnt = 0
    for s in shifts:
        v = abs(float(np.dot(ra_c, np.roll(rb_c, int(s)))) / den)
        cnt += v >= obs
    return obs, float((cnt + 1) / (n_perm + 1))


def boot_ci(v, n_boot=10000, seed=1):
    v = np.asarray([x for x in v if np.isfinite(x)], dtype=float)
    if v.size < 2:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(v, v.size, replace=True).mean() for _ in range(n_boot)])
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


# ---------------------------------------------------------------- per-session extraction

def session_features(path, window_ms=(-500.0, 0.0), max_trials=None, lfp_probe="probe_0"):
    with h5py.File(path, "r") as h:
        pupil_grp = h["acquisition/pupil_1_tracking"]
        gaze_grp = h["acquisition/eye_1_tracking"]
        st_ds = _find(pupil_grp, "starting_time")
        rate = float(st_ds.attrs["rate"])
        start_s = float(st_ds[()])
        pupil = _find(pupil_grp, "data")
        gaze = _find(gaze_grp, "data")
        lfp = _find(h[f"acquisition/{lfp_probe}_lfp"], "data")
        muae = _find(h[f"acquisition/{lfp_probe}_muae"], "data")
        n_tot = int(pupil.shape[0])

        trials = trial_onsets(h)
        if max_trials:
            trials = trials.iloc[:max_trials]

        n_win = int(round((window_ms[1] - window_ms[0]) / 1000.0 * rate))
        rows = []
        for _, r in trials.iterrows():
            i0 = int(round((float(r["start_time"]) + window_ms[0] / 1000.0 - start_s) * rate))
            i1 = i0 + n_win
            if i0 < 0 or i1 > n_tot:
                continue
            p = np.asarray(pupil[i0:i1], dtype=np.float64)
            g = np.asarray(gaze[i0:i1, :], dtype=np.float64)
            L = np.asarray(lfp[i0:i1, :], dtype=np.float64)
            M = np.asarray(muae[i0:i1, :], dtype=np.float64)
            # LFP broadband power: mean power over channels, LOG TAKEN ONCE AT THE END
            lfp_pow = float(np.mean(np.var(L, axis=0)))
            muae_mean = float(np.mean(M))
            rows.append({
                "trial_num": int(r["trial_num"]),
                "onset_s": float(r["start_time"]),
                "i0": i0,
                "pupil_mean": float(p.mean()),
                "pupil_sd": float(p.std()),
                "pupil_slope": ols_slope(p),
                "gaze_x": float(g[:, 0].mean()),
                "gaze_y": float(g[:, 1].mean()),
                "gaze_sd": float(np.hypot(g[:, 0].std(), g[:, 1].std())),
                "lfp_logpower": float(np.log10(lfp_pow)) if lfp_pow > 0 else np.nan,
                "muae_logmean": float(np.log10(muae_mean)) if muae_mean > 0 else np.nan,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # gaze distance from the SESSION's own median gaze position
        cx, cy = df["gaze_x"].median(), df["gaze_y"].median()
        df["gaze_dist"] = np.hypot(df["gaze_x"] - cx, df["gaze_y"] - cy)

        # population firing rate in the same strictly pre-event window
        u = h.get("units")
        if u is not None and "spike_times" in u:
            stimes = u["spike_times"][:]
            sidx = np.asarray(u["spike_times_index"][:], dtype=np.int64)
            snr = _num(u, "snr") if "snr" in u else np.full(sidx.size, np.nan)
            fr = _num(u, "firing_rate") if "firing_rate" in u else np.full(sidx.size, np.nan)
            pres = _num(u, "presence_ratio") if "presence_ratio" in u else np.full(sidx.size, np.nan)
            keep = np.flatnonzero((snr > 0.5) & (fr > 0.5) & (pres >= 0.98))
            starts = np.concatenate(([0], sidx[:-1]))
            wl = (window_ms[1] - window_ms[0]) / 1000.0
            t_lo = df["onset_s"].to_numpy() + window_ms[0] / 1000.0
            t_hi = df["onset_s"].to_numpy() + window_ms[1] / 1000.0
            total = np.zeros(len(df))
            for ui in keep:
                s = np.sort(stimes[starts[ui]:sidx[ui]])
                total += np.searchsorted(s, t_hi) - np.searchsorted(s, t_lo)
            df["pop_rate_hz"] = total / (wl * max(len(keep), 1))
            df.attrs["n_units_used"] = int(keep.size)
        else:
            df["pop_rate_hz"] = np.nan
            df.attrs["n_units_used"] = 0
    return df


BEH = ["pupil_mean", "pupil_sd", "pupil_slope", "gaze_dist", "gaze_sd"]
NEU = ["lfp_logpower", "muae_logmean", "pop_rate_hz"]


def analyse_session(df, stem):
    ok = df[BEH + NEU].replace([np.inf, -np.inf], np.nan).dropna()
    n = len(ok)
    out = {"session": stem, "subject": stem.split("_")[0].removeprefix("sub-"),
           "n_trials": int(n), "n_units_used": int(df.attrs.get("n_units_used", 0))}
    if n < 60:
        out["skipped"] = "n<60"
        return out
    X = ok[BEH].to_numpy()
    multi, pairs, ceiling, negctrl = {}, [], {}, {}
    for nf in NEU:
        y = ok[nf].to_numpy()
        if np.std(y) == 0:
            continue
        r2b = cv_r2(X, y, blocked=True)
        r2r = cv_r2(X, y, blocked=False)
        multi[nf] = {
            "cv_r2_blocked": r2b,
            "cv_r2_random": r2r,
            "r_effective_blocked": float(np.sqrt(max(r2b, 0.0))),
            "r_effective_random": float(np.sqrt(max(r2r, 0.0))),
        }
        # negative control: half-session circular shift of the design matrix
        Xs = np.roll(X, n // 2, axis=0)
        negctrl[nf] = cv_r2(Xs, y, blocked=True)
        # per-pair
        for bf in BEH:
            a = ok[bf].to_numpy()
            r, p = circshift_perm_p(a, y, n_perm=2000, seed=abs(hash((stem, bf, nf))) % (2 ** 31))
            pairs.append({"behavior": bf, "neural": nf, "n": int(n),
                          "abs_rank_pearson": r,
                          "signed_rank_pearson": rank_pearson(a, y),
                          "p_circshift": p})
        # ceiling: predict this neural feature from the OTHER neural features
        others = [c for c in NEU if c != nf]
        Xn = ok[others].to_numpy()
        ceiling[nf] = {"from": others, "cv_r2_blocked": cv_r2(Xn, y, blocked=True)}
    out["multivariate"] = multi
    out["pairwise"] = pairs
    out["neural_ceiling"] = ceiling
    out["negative_control_shifted_behavior"] = negctrl
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-trials", type=int, default=None)
    args = ap.parse_args()

    import omission as oa
    from jnwb import StatisticalAnalysis

    nwb_dir = oa.paths.nwb_dir()
    results = []
    module_crosscheck = []
    for stem in args.sessions:
        path = nwb_dir / f"{stem}.nwb"
        df = session_features(path, max_trials=args.max_trials)
        res = analyse_session(df, stem)
        results.append(res)
        # cross-check my pupil_mean against the module's, same window
        try:
            from omission.jnwb_ext import behavioral_covariates as bc
            b = bc.load_pupil_epochs(path, alignment="p1", window_ms=(-500.0, 0.0),
                                     missing_data="drop")
            f = bc.extract_pupil_features(b)
            m = f.assign(trial_num=[int(t.split("trial=")[1].split("|")[0])
                                    for t in f["trial_id"]])
            j = df[["trial_num", "pupil_mean"]].merge(m[["trial_num", "mean"]], on="trial_num")
            module_crosscheck.append({
                "session": stem, "n_matched": int(len(j)),
                "max_abs_diff": float(np.nanmax(np.abs(j["pupil_mean"] - j["mean"]))),
                "pearson_r": float(np.corrcoef(j["pupil_mean"], j["mean"])[0, 1]),
            })
        except Exception as exc:  # noqa: BLE001
            module_crosscheck.append({"session": stem, "error": f"{type(exc).__name__}: {exc}"})
        print("done", stem, res.get("n_trials"), flush=True)

    # -------- family-wide multiplicity over ALL pairwise tests --------
    flat = []
    for r in results:
        for p in r.get("pairwise", []):
            flat.append({**p, "session": r["session"], "subject": r["subject"]})
    if flat:
        praw = [x["p_circshift"] for x in flat]
        q = StatisticalAnalysis.fdr_correct(praw)
        q = np.asarray(q["fdr_pvals"] if isinstance(q, dict) else q, dtype=float)
        for x, qq in zip(flat, q):
            x["q_bh"] = float(qq)

    # -------- session-level summary (session = inferential unit) --------
    summary = {}
    for nf in NEU:
        vals = [r["multivariate"][nf]["cv_r2_blocked"] for r in results
                if r.get("multivariate", {}).get(nf) is not None]
        reff = [r["multivariate"][nf]["r_effective_blocked"] for r in results
                if r.get("multivariate", {}).get(nf) is not None]
        neg = [r["negative_control_shifted_behavior"][nf] for r in results
               if nf in r.get("negative_control_shifted_behavior", {})]
        ceil = [r["neural_ceiling"][nf]["cv_r2_blocked"] for r in results
                if nf in r.get("neural_ceiling", {})]
        summary[nf] = {
            "n_sessions": len(vals),
            "cv_r2_blocked_per_session": vals,
            "cv_r2_blocked_mean": float(np.nanmean(vals)) if vals else None,
            "cv_r2_blocked_median": float(np.nanmedian(vals)) if vals else None,
            "cv_r2_blocked_ci95_boot_over_sessions": boot_ci(vals),
            "r_effective_per_session": reff,
            "r_effective_mean": float(np.nanmean(reff)) if reff else None,
            "r_effective_max": float(np.nanmax(reff)) if reff else None,
            "negctrl_cv_r2_mean": float(np.nanmean(neg)) if neg else None,
            "neural_ceiling_cv_r2_mean": float(np.nanmean(ceil)) if ceil else None,
        }
    absr = [x["abs_rank_pearson"] for x in flat]
    pw = {
        "n_tests": len(flat),
        "abs_rank_pearson_median": float(np.median(absr)) if absr else None,
        "abs_rank_pearson_p90": float(np.percentile(absr, 90)) if absr else None,
        "abs_rank_pearson_max": float(np.max(absr)) if absr else None,
        "n_sig_raw_p05": int(sum(x["p_circshift"] < 0.05 for x in flat)),
        "n_sig_bh_q05": int(sum(x.get("q_bh", 1) < 0.05 for x in flat)),
    }

    Path(args.out).write_text(json.dumps({
        "window_ms": [-500.0, 0.0],
        "per_session": results,
        "pairwise_flat": flat,
        "session_level_summary": summary,
        "pairwise_summary": pw,
        "module_crosscheck": module_crosscheck,
    }, indent=1), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
