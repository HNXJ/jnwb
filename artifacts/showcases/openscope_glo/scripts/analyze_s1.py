"""Showcase 1: the identical sequence in three contexts (PREREGISTRATION.md).

Usage: python scripts/analyze_s1.py [responsive|all]
Reads results/sessions/*/ and writes results/s1/ (or s1_allunits_exploratory/): confirmatory.csv, drift.csv,
exploratory_*.csv, per_mouse.csv and receipt.json.
"""
import json
import sys
import time

import numpy as np
import pandas as pd

from glo_common import AREAS, RESULTS, SEED, assets, receipt, sha256
import jnwb

W = slice(30, 50)  # 10-ms bins covering 50-250 ms after onset (window starts at -250 ms)
MIN_UNITS, MIN_MICE = 5, 6
# "responsive" is the preregistered population; "all" (every quality-passing visual unit) is a
# post-hoc exploratory variant written to its own folder.
POPULATION = sys.argv[1] if len(sys.argv) > 1 else "responsive"
assert POPULATION in ("responsive", "all")
OUT = RESULTS / ("s1" if POPULATION == "responsive" else "s1_allunits_exploratory")
CONTRASTS = ["C1_main_vs_random_xxxx", "C2_main_vs_seq_xxxx", "C3_random_vs_seq_xxxx", "C4_random_vs_seq_yyyy"]


def load(ses):
    d = RESULTS / "sessions" / ses
    meta = json.load(open(d / "session.json"))
    cond = pd.read_csv(d / "conditions.csv", keep_default_na=False)
    zf = np.load(d / "counts.npz")
    kept = cond[cond.excluded == ""].reset_index(drop=True)
    assert np.array_equal(kept["seq"].to_numpy(), zf["seq"]), "counts and conditions disagree"
    keep = zf["responsive"] if POPULATION == "responsive" else np.ones(len(zf["area"]), bool)
    z = {"p3": zf["p3"][keep], "p4": zf["p4"][keep]}
    r3 = z["p3"][:, :, W].sum(axis=2) / 0.2
    r4 = z["p4"][:, :, W].sum(axis=2) / 0.2
    return meta, kept, zf["area"][keep], r4 - r3, z, sha256(d / "counts.npz")


def delta(d, kept, mask):
    """Per-unit mean over the selected sequences of rate(P4) - rate(P3); NaN without trials."""
    return d[:, mask].mean(axis=1) if mask.any() else np.full(d.shape[0], np.nan)


def unit_contrasts(kept, d, main_mask=None, keep=None):
    keep = np.ones(len(kept), bool) if keep is None else keep
    ctx, pat = kept.context.to_numpy(), kept.pattern.to_numpy()
    main = np.isin(ctx, ["main1", "main2"]) if main_mask is None else main_mask
    sel = lambda m, p: m & (pat == p) & keep  # noqa: E731
    dm = delta(d, kept, sel(main, "xxxx"))
    dr = delta(d, kept, sel(ctx == "random", "xxxx"))
    ds = delta(d, kept, sel(ctx == "seq", "xxxx"))
    dry = delta(d, kept, sel(ctx == "random", "yyyy"))
    dsy = delta(d, kept, sel(ctx == "seq", "yyyy"))
    d1 = delta(d, kept, sel(ctx == "main1", "xxxx"))
    d2 = delta(d, kept, sel(ctx == "main2", "xxxx"))
    return {CONTRASTS[0]: dm - dr, CONTRASTS[1]: dm - ds, CONTRASTS[2]: dr - ds, CONTRASTS[3]: dry - dsy,
            "D_main1_vs_main2_xxxx": d1 - d2}


def per_mouse(sessions, opts=None):
    """Per mouse, area and contrast: median over units. `opts(kept)` gives unit_contrasts kwargs."""
    rows = []
    for ses, (meta, kept, area, d, _, _) in sessions.items():
        uc = unit_contrasts(kept, d, **(opts(kept) if opts else {}))
        for a in AREAS:
            m = area == a
            for name, v in uc.items():
                vals = v[m]
                vals = vals[np.isfinite(vals)]
                rows.append({"session": ses, "mouse": meta["subject_id"], "area": a, "contrast": name,
                             "n_units": int(len(vals)), "median": float(np.median(vals)) if len(vals) else np.nan})
    return pd.DataFrame(rows)


def bootstrap_ci(x, rng):
    idx = rng.integers(0, len(x), size=(10000, len(x)))
    return np.percentile(x[idx].mean(axis=1), [2.5, 97.5])


def test(pm, contrasts):
    rng = np.random.default_rng(SEED)
    rows = []
    for c in contrasts:
        for a in AREAS:
            s = pm[(pm.contrast == c) & (pm.area == a) & (pm.n_units >= MIN_UNITS)]
            x = s["median"].to_numpy()
            row = {"contrast": c, "area": a, "n_mice": len(x), "n_units": int(s.n_units.sum())}
            if len(x) >= MIN_MICE:
                mean, p, floor = jnwb.exact_sign_flip(x, alternative="two-sided")
                lo, hi = bootstrap_ci(x, rng)
                row.update(mean_hz=mean, ci_lo=lo, ci_hi=hi, p=p, p_floor=floor,
                           n_positive=int((x > 0).sum()))
            rows.append(row)
    t = pd.DataFrame(rows)
    ok = t["p"].notna() if "p" in t else pd.Series(False, index=t.index)
    t["q"] = np.nan
    if ok.any():
        t.loc[ok, "q"] = jnwb.fdr_correct(t.loc[ok, "p"].to_numpy())
    return t


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    a = assets()
    sessions, excluded = {}, {}
    for ses in sorted(a):
        meta = json.load(open(RESULTS / "sessions" / ses / "session.json"))
        if not (meta["validation"]["pass"] and meta["clock_pass"]):
            excluded[ses] = {"validation": meta["validation"], "clock_ms": meta["clock_check_ms"]}
            continue
        sessions[ses] = load(ses)
    mice = [s[0]["subject_id"] for s in sessions.values()]
    if len(set(mice)) != len(mice):
        raise SystemExit("more than one session per mouse")
    if len(sessions) < 10:
        raise SystemExit(f"STOP: {len(sessions)} sessions pass inclusion")

    pm = per_mouse(sessions)
    pm.to_csv(OUT / "per_mouse.csv", index=False)
    conf = test(pm, CONTRASTS)
    drift = test(pm, ["D_main1_vs_main2_xxxx"]).drop(columns="q")
    dmap = drift.set_index("area")["mean_hz"] if "mean_hz" in drift else pd.Series(dtype=float)
    conf["drift_mean_hz"] = conf.area.map(dmap)
    conf["identified"] = np.where(
        conf.contrast.isin(CONTRASTS[:2]) & (conf.q < 0.05),
        np.where(conf.mean_hz.abs() > conf.drift_mean_hz.abs(), "identified", "not identified from drift"), "")
    conf.to_csv(OUT / "confirmatory.csv", index=False)
    drift.to_csv(OUT / "drift.csv", index=False)

    # Exploratory 1: history-matched main (xxxx preceded by xxxy in main).
    def hist(kept):
        ctx = kept.context.to_numpy()
        return {"main_mask": np.isin(ctx, ["main1", "main2"]) & (kept.prev_pattern.to_numpy() == "xxxy")}
    test(per_mouse(sessions, hist), CONTRASTS[:2]).to_csv(OUT / "exploratory_history_matched.csv", index=False)

    # Exploratory 2: running-speed shared range across main, random and seq.
    drop = []

    def run_keep(kept):
        sp = kept.run_speed_pre_p4.to_numpy(dtype=float)
        ctx = kept.context.to_numpy()
        groups = [np.isin(ctx, ["main1", "main2"]), ctx == "random", ctx == "seq"]
        lo = max(np.nanmin(sp[g]) for g in groups)
        hi = min(np.nanmax(sp[g]) for g in groups)
        keep = (sp >= lo) & (sp <= hi)
        drop.append({"range_lo_cm_s": lo, "range_hi_cm_s": hi, "n_kept": int(keep.sum()), "n_dropped": int((~keep).sum()),
                     **{f"median_speed_{n}": float(np.nanmedian(sp[g])) for n, g in zip(["main", "random", "seq"], groups)}})
        return {"keep": keep}

    test(per_mouse(sessions, run_keep), CONTRASTS).to_csv(OUT / "exploratory_running_matched.csv", index=False)
    pd.DataFrame(drop, index=list(sessions)).to_csv(OUT / "running_range.csv", index_label="session")

    # Exploratory 3: per-unit prevalence of C2 (main xxxx vs seq xxxx, trial-level shuffle).
    rng = np.random.default_rng(SEED)
    prev = []
    for ses, (meta, kept, area, d, _, _) in sessions.items():
        ctx, pat = kept.context.to_numpy(), kept.pattern.to_numpy()
        mm = np.isin(ctx, ["main1", "main2"]) & (pat == "xxxx")
        ss = (ctx == "seq") & (pat == "xxxx")
        for i in range(d.shape[0]):
            diff, p = jnwb.shuffle_pvalue_unpaired(d[i, mm], d[i, ss], n_shuffles=1000, rng=rng)
            prev.append({"session": ses, "area": area[i], "diff_hz": diff, "p": p})
    prev = pd.DataFrame(prev)
    prow = []
    for ar in AREAS:
        s = prev[prev.area == ar]
        k_pos = int(((s.p < 0.05) & (s.diff_hz > 0)).sum()); k_neg = int(((s.p < 0.05) & (s.diff_hz < 0)).sum())
        n = len(s)
        lo, hi = jnwb.clopper_pearson(k_pos, n) if n else (np.nan, np.nan)
        prow.append({"area": ar, "n_units": n, "k_pos_p05": k_pos, "k_neg_p05": k_neg, "frac_pos": k_pos / n if n else np.nan,
                     "cp_lo": lo, "cp_hi": hi})
    pd.DataFrame(prow).to_csv(OUT / "exploratory_prevalence_C2.csv", index=False)

    # Exploratory 4: time-resolved C2, cluster permutation paired over mice.
    crow = []
    for ar in AREAS:
        X, Y = [], []
        for ses, (meta, kept, area, d, z, _) in sessions.items():
            m = area == ar
            if m.sum() < MIN_UNITS:
                continue
            ctx, pat = kept.context.to_numpy(), kept.pattern.to_numpy()
            mm = np.isin(ctx, ["main1", "main2"]) & (pat == "xxxx")
            ss = (ctx == "seq") & (pat == "xxxx")
            dd = (z["p4"][m].astype(float) - z["p3"][m].astype(float)) / 0.01  # Hz per 10-ms bin
            X.append(np.median(dd[:, mm].mean(axis=1), axis=0))
            Y.append(np.median(dd[:, ss].mean(axis=1), axis=0))
        if len(X) < MIN_MICE:
            crow.append({"area": ar, "n_mice": len(X)})
            continue
        res = jnwb.cluster_permutation_test(np.array(X), np.array(Y), paired=True, n_permutations=1000,
                                            rng=np.random.default_rng(SEED), tail="both")
        t_ms = -250 + 10 * np.arange(75) + 5
        for c in res["clusters"]:
            span = t_ms[c["mask"]]
            crow.append({"area": ar, "n_mice": len(X), "cluster_stat": c["statistic"], "p": c["p_value"],
                         "start_ms": float(span.min()), "end_ms": float(span.max())})
        if not res["clusters"]:
            crow.append({"area": ar, "n_mice": len(X), "cluster_stat": np.nan, "p": np.nan})
    pd.DataFrame(crow).to_csv(OUT / "exploratory_time_resolved_C2.csv", index=False)

    # Exploratory 5: positive control with the P4 stimulus matched. In the randomized control,
    # rate(P4) of yyyx minus rate(P4) of xxxx: the same grating x after three y or three x
    # (stimulus-specific adaptation), both at 12.5 %. Same for y: xxxy minus yyyy.
    rows = []
    for ses, (meta, kept, area, d, z, _) in sessions.items():
        r4 = z["p4"][:, :, W].sum(axis=2) / 0.2
        ctx, pat = kept.context.to_numpy(), kept.pattern.to_numpy()
        mean4 = lambda p: r4[:, (ctx == "random") & (pat == p)].mean(axis=1)  # noqa: E731
        for name, v in {"PC_SSA_x_random_yyyx_vs_xxxx_P4": mean4("yyyx") - mean4("xxxx"),
                        "PC_SSA_y_random_xxxy_vs_yyyy_P4": mean4("xxxy") - mean4("yyyy")}.items():
            for ar in AREAS:
                vals = v[area == ar]
                rows.append({"session": ses, "mouse": meta["subject_id"], "area": ar, "contrast": name,
                             "n_units": len(vals), "median": float(np.median(vals)) if len(vals) else np.nan})
    test(pd.DataFrame(rows), ["PC_SSA_x_random_yyyx_vs_xxxx_P4", "PC_SSA_y_random_xxxy_vs_yyyy_P4"]).to_csv(
        OUT / "exploratory_positive_control_SSA.csv", index=False)

    # Exploratory 6: spike-stimulus clock sanity, onset latency of the population PSTH at P3.
    lat = []
    t_ms = -250 + 10 * np.arange(40) + 5  # bin centres, -245 .. 145 ms
    for ses, (meta, kept, area, d, z, _) in sessions.items():
        for name, m in [("VISp", area == "VISp"), ("all_visual", np.ones(len(area), bool))]:
            if m.sum() < MIN_UNITS:
                continue
            psth = z["p3"][m][:, :, :40].astype(float).mean(axis=(0, 1)) / 0.01
            f = jnwb.fit_exponential_onset(t_ms, psth, t0_bounds_ms=(0.0, 140.0), baseline_window_ms=(-250.0, 0.0))
            lat.append({"session": ses, "population": name, "n_units": int(m.sum()), "t0_ms": f["t0"],
                        "tau_ms": f["tau"], "r2": f["r2"], "converged": f["converged"]})
    pd.DataFrame(lat).to_csv(OUT / "exploratory_onset_latency_P3.csv", index=False)

    rec = receipt({"inputs": {ses: {"asset_id": s[0]["asset_id"], "dandi_sha256": s[0]["dandi_sha256"],
                                    "counts_npz_sha256": s[5], "extract_script_commit": s[0]["script_commit"]}
                              for ses, s in sessions.items()},
                   "excluded_sessions": excluded, "n_sessions": len(sessions), "population": POPULATION,
                   "min_units": MIN_UNITS, "min_mice": MIN_MICE, "seconds": round(time.time() - t0, 1)})
    json.dump(rec, open(OUT / "receipt.json", "w"), indent=1, default=str)
    pd.set_option("display.width", 200)
    print(conf.to_string())
    print(drift.to_string())


if __name__ == "__main__":
    main()
