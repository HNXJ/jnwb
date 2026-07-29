r"""
Step 3d -- the inferential backbone for omission-a's LFP results.

ONE MODEL FAMILY. Every number this script produces comes from a Gaussian-family mixed model
with an identity link (a linear mixed model, the Gaussian case of the GLMM backbone declared
in the manuscript Methods), fitted with statsmodels MixedLM by REML. Proportions are reported
with Clopper-Pearson exact binomial intervals. Nothing else is inferential.

INPUT
    outputs/lfp_band_census_v2/channel_band_power.csv.gz   (build with
    scripts/build_channel_area_vector.py then compute_channel_band_power_census_v2.py)

    Response: db_mid_omirel -- power in the omitted slot relative to the -250..-50 ms
    omission-relative baseline, in dB, averaged over trials within a channel.

UNIT OF INFERENCE
    Channels within a probe within a session within a subject are nested and are NOT
    independent. Every model carries a random intercept for session (and, where the design
    permits, for probe within session). With three subjects, subject cannot support a
    random effect -- three levels cannot identify a variance component -- so subject is
    handled by stratification and by the within-subject contrast in model D, never by a
    three-level random term.

MODELS
    A  per band, corpus-wide:   db ~ 1 + (1 | session/probe)
       Tests H0 that power in the omitted slot equals the preceding-delay baseline.
    B  per band, per subject:   db ~ 1 + (1 | session/probe), fitted within each subject.
       Shows whether the corpus-wide effect is carried by one animal.
    C  per band, area effects:  db ~ C(area) + (1 | session/probe)
       Reported DESCRIPTIVELY. Area and subject are confounded in this corpus (several areas
       are recorded in only one animal), so a between-area coefficient is not separable from
       a between-animal difference. Stated, not laundered.
    D  per band, the defensible V3 contrast: within a single subject, channels on the V3a/V3d
       probe vs channels on the V1/V2 probe of the SAME sessions.
       db ~ probe_group + (1 | session). This is the only V3 comparison in which subject,
       session, day and rig are held constant.
    E  per band, laminar:       db ~ C(putative_layer) + (1 | session/probe)
       Fitted only if vFLIP layer coverage is adequate; skipped with a stated reason if not.

MULTIPLICITY
    The declared family is the five bands within each model. p-values are corrected across
    bands with Benjamini-Hochberg, which controls the false discovery rate -- NOT the
    family-wise error rate. Both the raw and adjusted values are emitted.

OUTPUT
    outputs/lfp_band_census_v2/glmm_results.json
    outputs/lfp_band_census_v2/glmm_summary.csv
"""
from __future__ import annotations

import json
import os
import platform
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.regression.mixed_linear_model import MixedLM

CENSUS = r"D:/workspace/omission/outputs/lfp_band_census_v2/channel_band_power.csv.gz"
AREA_VEC = r"D:/workspace/omission/outputs/channel_area_vector/channel_area_vector.csv"
OUT_DIR = r"D:/workspace/omission/outputs/lfp_band_census_v2"
BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]
RESP = "db_mid_omirel"


def bh(pvals):
    """Benjamini-Hochberg adjusted p-values. Controls FDR, not FWER."""
    p = np.asarray(pvals, dtype=float)
    ok = np.isfinite(p)
    out = np.full(p.shape, np.nan)
    if ok.sum() == 0:
        return out
    q = p[ok]
    n = q.size
    order = np.argsort(q)
    adj = np.minimum.accumulate((q[order] * n / np.arange(n, 0, -1))[::-1])[::-1]
    res = np.empty(n)
    res[order] = np.clip(adj, 0, 1)
    out[ok] = res
    return out


def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (np.nan, np.nan)
    lo = 0.0 if k == 0 else stats.beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def fit_mixed(d: pd.DataFrame, formula: str, group: str, vc: dict | None = None):
    """REML fit; returns None with a reason if the design cannot support the model."""
    d = d.dropna(subset=[RESP, group])
    if d[group].nunique() < 3:
        return None, f"only {d[group].nunique()} groups"
    if len(d) < 20:
        return None, f"only {len(d)} observations"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            md = MixedLM.from_formula(formula, groups=d[group], vc_formula=vc, data=d)
            res = md.fit(reml=True, method="lbfgs")
        return res, None
    except Exception as e:
        return None, f"fit failed: {type(e).__name__}: {e}"


def coef_rows(res, model, band, extra=None):
    rows = []
    for name in res.params.index:
        if name.startswith("Group") or name in ("probe Var", "Group Var"):
            continue
        rows.append({
            "model": model, "band": band, "term": name,
            "estimate_db": float(res.params[name]), "se": float(res.bse[name]),
            "z": float(res.tvalues[name]), "p_raw": float(res.pvalues[name]),
            "ci_lo": float(res.conf_int().loc[name, 0]),
            "ci_hi": float(res.conf_int().loc[name, 1]),
            **(extra or {}),
        })
    return rows


def main():
    if not os.path.exists(CENSUS):
        raise SystemExit(f"missing {CENSUS} -- run compute_channel_band_power_census_v2.py")
    df = pd.read_csv(CENSUS)
    df["probe_id"] = df["session_prefix"] + ":" + df["probe"]

    # Layers are joined here rather than taken from the census column, because the vFLIP
    # products are regenerated independently of the (expensive) census run.
    if os.path.exists(AREA_VEC):
        av = pd.read_csv(AREA_VEC)
        if "putative_layer" in av.columns:
            df = df.drop(columns=["putative_layer"], errors="ignore").merge(
                av[["session_prefix", "probe_letter", "channel", "putative_layer"]]
                .rename(columns={"probe_letter": "probe"}),
                on=["session_prefix", "probe", "channel"], how="left")

    # V3d and V3a are the two halves of one shank under an assumed equal-share partition
    # (artifacts/.lab/channel_area_vector_uniform_split_finding_20260728.json). Pooling them
    # for inference; the census keeps them separate for descriptive displays.
    df["area_infer"] = df["area"].replace({"V3d": "V3a/d", "V3a": "V3a/d"})

    rows, notes = [], []

    # ---- A: corpus-wide, per band -------------------------------------------------
    for b in BANDS:
        d = df[df.band == b]
        res, why = fit_mixed(d, f"{RESP} ~ 1", "session_prefix",
                             vc={"probe": "0 + C(probe_id)"})
        if res is None:
            notes.append(f"A/{b}: {why}")
            continue
        rows += coef_rows(res, "A_corpus", b,
                          {"n_obs": int(len(d)), "n_sessions": int(d.session_prefix.nunique())})

    # ---- B: per subject, per band -------------------------------------------------
    for subj, ds in df.groupby("subject"):
        for b in BANDS:
            d = ds[ds.band == b]
            res, why = fit_mixed(d, f"{RESP} ~ 1", "session_prefix",
                                 vc={"probe": "0 + C(probe_id)"})
            if res is None:
                notes.append(f"B/{subj}/{b}: {why}")
                continue
            rows += coef_rows(res, "B_within_subject", b,
                              {"subject": subj, "n_obs": int(len(d)),
                               "n_sessions": int(d.session_prefix.nunique())})

    # ---- C: area effects, descriptive --------------------------------------------
    ref = "V1" if "V1" in set(df.area_infer) else sorted(df.area_infer.unique())[0]
    for b in BANDS:
        d = df[df.band == b].copy()
        d["area"] = pd.Categorical(d["area_infer"],
                                   categories=[ref] + sorted(set(d.area_infer) - {ref}))
        res, why = fit_mixed(d, f"{RESP} ~ C(area)", "session_prefix",
                             vc={"probe": "0 + C(probe_id)"})
        if res is None:
            notes.append(f"C/{b}: {why}")
            continue
        rows += coef_rows(res, "C_area_descriptive", b,
                          {"reference_area": ref, "n_obs": int(len(d))})

    # ---- D: the defensible V3 contrast -------------------------------------------
    v3_areas = {"V3", "V3a", "V3d"}
    early = {"V1", "V2"}
    d_rows = []
    for subj, ds in df.groupby("subject"):
        sess_ok = []
        for sp, dg in ds.groupby("session_prefix"):
            has_v3 = dg[dg.area.isin(v3_areas)]["probe_id"].nunique() > 0
            has_early = dg[dg.area.isin(early)]["probe_id"].nunique() > 0
            # require the two area groups to sit on DIFFERENT probes in the same session
            if has_v3 and has_early:
                pv = set(dg[dg.area.isin(v3_areas)]["probe_id"])
                pe = set(dg[dg.area.isin(early)]["probe_id"])
                if pv - pe and pe - pv:
                    sess_ok.append(sp)
        if len(sess_ok) < 3:
            notes.append(f"D/{subj}: only {len(sess_ok)} sessions with V3 and V1/V2 on "
                         f"separate probes; contrast not fitted")
            continue
        sub = ds[ds.session_prefix.isin(sess_ok)].copy()
        sub = sub[sub.area.isin(v3_areas | early)]
        sub["probe_group"] = np.where(sub.area.isin(v3_areas), "V3", "V1V2")
        sub["probe_group"] = pd.Categorical(sub["probe_group"], categories=["V1V2", "V3"])
        for b in BANDS:
            d = sub[sub.band == b]
            res, why = fit_mixed(d, f"{RESP} ~ C(probe_group)", "session_prefix")
            if res is None:
                notes.append(f"D/{subj}/{b}: {why}")
                continue
            d_rows += coef_rows(res, "D_within_subject_V3_vs_V1V2", b,
                                {"subject": subj, "n_sessions": len(sess_ok),
                                 "n_obs": int(len(d))})
    rows += d_rows

    # ---- E: laminar ---------------------------------------------------------------
    cov = float(df["putative_layer"].notna().mean())
    if cov < 0.5:
        notes.append(f"E: laminar model skipped -- vFLIP layer coverage is {cov:.1%} of "
                     f"channels; a laminar claim on partial coverage would be selection, "
                     f"not anatomy")
    else:
        dl = df[df.putative_layer.notna() & (df.putative_layer != "na")].copy()
        for b in BANDS:
            d = dl[dl.band == b]
            res, why = fit_mixed(d, f"{RESP} ~ C(putative_layer)", "session_prefix",
                                 vc={"probe": "0 + C(probe_id)"})
            if res is None:
                notes.append(f"E/{b}: {why}")
                continue
            rows += coef_rows(res, "E_laminar", b, {"n_obs": int(len(d))})

    # ---- session-level companions -------------------------------------------------
    # Models A, C and D above are fitted on individual channels. Channels within a probe
    # are strongly dependent -- neighbouring contacts on one shank see overlapping field
    # potentials -- so their standard errors are anti-conservative, and in C and D
    # implausibly so (|z| above 40 on a sub-dB effect). The companions below collapse to
    # one observation per session (per area, per probe group) BEFORE fitting, so the
    # effective sample size is the number of sessions. These are the numbers to report.
    agg_rows = []
    for b in BANDS:
        d = df[df.band == b]

        s = d.groupby("session_prefix", as_index=False)[RESP].mean()
        if len(s) >= 3:
            t = stats.ttest_1samp(s[RESP], 0.0)
            ci = stats.t.interval(0.95, len(s) - 1, loc=s[RESP].mean(),
                                  scale=stats.sem(s[RESP]))
            agg_rows.append({"model": "A_session_level", "band": b, "term": "Intercept",
                             "estimate_db": float(s[RESP].mean()), "se": float(stats.sem(s[RESP])),
                             "z": float(t.statistic), "p_raw": float(t.pvalue),
                             "ci_lo": float(ci[0]), "ci_hi": float(ci[1]),
                             "n_obs": int(len(s)), "n_sessions": int(len(s))})

        for subj, ds in d.groupby("subject"):
            ss = ds.groupby("session_prefix", as_index=False)[RESP].mean()
            if len(ss) < 3:
                notes.append(f"B_session_level/{subj}/{b}: only {len(ss)} sessions")
                continue
            t = stats.ttest_1samp(ss[RESP], 0.0)
            ci = stats.t.interval(0.95, len(ss) - 1, loc=ss[RESP].mean(),
                                  scale=stats.sem(ss[RESP]))
            agg_rows.append({"model": "B_session_level", "band": b, "term": "Intercept",
                             "estimate_db": float(ss[RESP].mean()),
                             "se": float(stats.sem(ss[RESP])), "z": float(t.statistic),
                             "p_raw": float(t.pvalue), "ci_lo": float(ci[0]),
                             "ci_hi": float(ci[1]), "subject": subj,
                             "n_obs": int(len(ss)), "n_sessions": int(len(ss))})

        sa = d.groupby(["session_prefix", "area_infer"], as_index=False)[RESP].mean()
        res, why = fit_mixed(sa.rename(columns={"area_infer": "area"}),
                             f"{RESP} ~ C(area, Treatment(reference='{ref}'))",
                             "session_prefix")
        if res is None:
            notes.append(f"C_session_level/{b}: {why}")
        else:
            agg_rows += coef_rows(res, "C_area_session_level", b,
                                  {"reference_area": ref, "n_obs": int(len(sa)),
                                   "n_sessions": int(sa.session_prefix.nunique())})

    # model D at session level, per subject that supported the channel-level fit
    for subj in {r.get("subject") for r in d_rows if r.get("subject")}:
        sub = df[(df.subject == subj) & df.area.isin(v3_areas | early)].copy()
        sub["probe_group"] = np.where(sub.area.isin(v3_areas), "V3", "V1V2")
        for b in BANDS:
            d = sub[sub.band == b]
            piv = (d.groupby(["session_prefix", "probe_group"], as_index=False)[RESP].mean()
                     .pivot(index="session_prefix", columns="probe_group", values=RESP)
                     .dropna())
            if len(piv) < 3:
                notes.append(f"D_session_level/{subj}/{b}: only {len(piv)} paired sessions")
                continue
            diff = piv["V3"] - piv["V1V2"]
            t = stats.ttest_rel(piv["V3"], piv["V1V2"])
            ci = stats.t.interval(0.95, len(diff) - 1, loc=diff.mean(),
                                  scale=stats.sem(diff))
            agg_rows.append({"model": "D_session_level_V3_vs_V1V2", "band": b,
                             "term": "V3 - V1V2", "estimate_db": float(diff.mean()),
                             "se": float(stats.sem(diff)), "z": float(t.statistic),
                             "p_raw": float(t.pvalue), "ci_lo": float(ci[0]),
                             "ci_hi": float(ci[1]), "subject": subj,
                             "n_obs": int(len(diff)), "n_sessions": int(len(diff))})

    out = pd.DataFrame(rows + agg_rows)
    # BH within (model, term, subject) across the five bands -- the declared family.
    # subject is filled so that rows without one form their own group rather than being
    # dropped by groupby's NaN handling.
    if "subject" not in out:
        out["subject"] = ""
    out["_subj"] = out["subject"].fillna("")
    out["p_bh"] = np.nan
    for _, g in out.groupby(["model", "term", "_subj"], dropna=False):
        out.loc[g.index, "p_bh"] = bh(g["p_raw"].values)
    out = out.drop(columns="_subj")

    # ---- descriptive: fraction of channels with |db| exceeding a fixed threshold ---
    prop = []
    for b in BANDS:
        d = df[df.band == b].dropna(subset=[RESP])
        for thr in (1.0,):
            k = int((d[RESP].abs() >= thr).sum())
            n = int(len(d))
            lo, hi = clopper_pearson(k, n)
            prop.append({"band": b, "threshold_db": thr, "k": k, "n": n,
                         "proportion": k / n if n else np.nan,
                         "ci95_lo": lo, "ci95_hi": hi,
                         "interval": "Clopper-Pearson exact binomial",
                         "caveat": "channels are nested within probes and sessions; this "
                                   "interval treats them as independent and therefore "
                                   "understates uncertainty. Descriptive only."})
        prop[-1]["median_db"] = float(d[RESP].median())
        prop[-1]["mean_db"] = float(d[RESP].mean())

    out.to_csv(os.path.join(OUT_DIR, "glmm_summary.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "input": CENSUS,
        "response": RESP,
        "response_definition": "10*log10(power in the omitted slot / power in the -250 to "
                               "-50 ms omission-relative baseline), dB, trial-averaged "
                               "within channel",
        "family": "Gaussian, identity link (linear mixed model; the Gaussian case of the "
                  "declared GLMM backbone)",
        "estimation": "statsmodels MixedLM, REML, lbfgs",
        "random_effects": "random intercept for session; variance component for probe within "
                          "session where the model permits",
        "subject_handling": "three subjects cannot identify a random-effect variance; subject "
                            "is handled by stratification (model B) and by the within-subject "
                            "contrast (model D)",
        "multiplicity": "Benjamini-Hochberg across the five bands within each (model, term). "
                        "Controls the false discovery rate, NOT the family-wise error rate.",
        "n_models_fitted": int(out.model.nunique()),
        "n_rows": int(len(out)),
        "descriptive_proportions": prop,
        "notes_and_skips": notes,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "statsmodels": sm.__version__,
                "platform": platform.platform()},
    }
    with open(os.path.join(OUT_DIR, "glmm_results.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(out.to_string(index=False))
    print("\nNOTES:")
    for n in notes:
        print("  -", n)
    print(f"\nWROTE {OUT_DIR}/glmm_summary.csv and glmm_results.json")
    return out


if __name__ == "__main__":
    main()
