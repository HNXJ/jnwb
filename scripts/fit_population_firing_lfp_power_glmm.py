r"""
GLMM on the population firing-rate x LFP band-power correlations (fig07 headline input).

Same backbone as fig05's area-hierarchy GLMM (fit_omission_band_power_glmm.py /
area_subject_glmm.py): Gaussian-family mixed model, identity link, statsmodels MixedLM by REML,
session as the random-intercept group, subject as an additive fixed effect (three subjects
cannot identify a random-effect variance component, so subject is never a random term here,
same reasoning as fig05).

RESPONSE
    Z = (real_r - null_mean) / null_std, one value per (session, condition_group, area,
    func_group, band) cell, from extract_population_firing_lfp_power_corr.py's trial-mismatch
    shuffle null. Already one row per session per cell -- no further within-session aggregation
    needed (unlike fig05's channel-level census, which required a session-level collapse first
    to avoid channel pseudo-replication).

MODEL
    z ~ C(area, Treatment(ref='V1')) + C(band, Treatment(ref='theta'))
        + C(func_group, Treatment(ref='Other')) + C(condition_group, Treatment(ref='baseline'))
        + C(subject), (1 | session)
    Main-effects only (no interactions) -- this project's own doctrine is to minimize the
    diversity of inferential frameworks and keep one model per question; a fully-crossed
    4-factor interaction model would fragment an already-partial-coverage design (585 cells,
    most with 3-8 sessions) into cells too sparse to estimate.

PAIRWISE CONTRASTS
    For each of area/band/func_group/condition_group, every pairwise level contrast is computed
    from the ONE fitted model (coef(A) - coef(B) via t_test), not by refitting per pair -- same
    approach as area_subject_glmm.fit_area_subject_and_pairwise.

MULTIPLICITY
    Two declared families, corrected separately: (1) the vs-reference coefficients from the
    main model, (2) all pairwise contrasts across all four factors together. Holm-Bonferroni
    (FWER) and Benjamini-Hochberg (FDR) both reported per family, not conflated.

OUTPUT
    outputs/population_firing_lfp_power_corr/glmm_summary.csv
    outputs/population_firing_lfp_power_corr/glmm_results.json
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
import statsmodels.formula.api as smf
from statsmodels.regression.mixed_linear_model import MixedLM
from statsmodels.stats.multitest import multipletests
from jnwb import paths as _P

IN_DIR = _P.REPO_ROOT / "outputs/population_firing_lfp_power_corr"
DATA_CSV = os.path.join(IN_DIR, "all_session_rows.csv.gz")
FACTORS = {"area": "V1", "band": "theta", "func_group": "Other", "condition_group": "baseline"}
ALPHA = 0.05


def fit_mixed(d, formula, group):
    d = d.dropna(subset=[group])
    if d[group].nunique() < 3 or len(d) < 20:
        return None, f"only {d[group].nunique()} groups / {len(d)} obs", None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            md = MixedLM.from_formula(formula, groups=d[group], data=d)
            res = md.fit(reml=True, method="lbfgs")
        return res, None, "MixedLM_REML"
    except Exception as e:
        why = f"fit failed: {type(e).__name__}: {e}"
        try:
            res = smf.ols(formula, data=d).fit(
                cov_type="cluster", cov_kwds={"groups": d[group]})
            return res, None, "OLS_cluster_robust_by_session"
        except Exception as e2:
            return None, f"{why}; OLS fallback also failed: {e2}", None


def coef_rows(res, model, extra=None):
    rows = []
    for name in res.params.index:
        if name.startswith("Group") or name in ("session Var", "Group Var"):
            continue
        rows.append({
            "model": model, "term": name,
            "estimate_z": float(res.params[name]), "se": float(res.bse[name]),
            "tstat": float(res.tvalues[name]), "p_raw": float(res.pvalues[name]),
            "ci_lo": float(res.conf_int().loc[name, 0]),
            "ci_hi": float(res.conf_int().loc[name, 1]),
            **(extra or {}),
        })
    return rows


def pairwise_rows(res, factor, levels, model_name):
    exog_names = list(res.model.exog_names)
    level_col = {}
    for name in exog_names:
        for lv in levels:
            if name == f"C({factor}, Treatment(reference='{FACTORS[factor]}'))[T.{lv}]":
                level_col[lv] = name
    all_levels = [FACTORS[factor]] + [lv for lv in levels if lv != FACTORS[factor]]
    rows = []
    for i, a in enumerate(all_levels):
        for b in all_levels[i + 1:]:
            contrast = np.zeros((1, len(exog_names)))
            if b != FACTORS[factor]:
                contrast[0, exog_names.index(level_col[b])] += 1.0
            if a != FACTORS[factor]:
                contrast[0, exog_names.index(level_col[a])] -= 1.0
            if not np.any(contrast):
                continue
            try:
                tt = res.t_test(contrast)
            except Exception:
                continue
            ci = np.ravel(tt.conf_int())
            rows.append({
                "model": model_name, "factor": factor, "term": f"{b} - {a}",
                "estimate_z": float(np.ravel(tt.effect)[0]), "se": float(np.ravel(tt.sd)[0]),
                "tstat": float(np.ravel(tt.tvalue)[0]), "p_raw": float(np.ravel(tt.pvalue)[0]),
                "ci_lo": float(ci[0]), "ci_hi": float(ci[1]),
            })
    return rows


def main():
    df = pd.read_csv(DATA_CSV)
    df["subject"] = df.session.str.extract(r"sub-([^_]+)_")
    df["area"] = pd.Categorical(df["area"], categories=[FACTORS["area"]] +
                                sorted(set(df.area) - {FACTORS["area"]}))
    df["band"] = pd.Categorical(df["band"], categories=[FACTORS["band"]] +
                                sorted(set(df.band) - {FACTORS["band"]}))
    df["func_group"] = pd.Categorical(df["func_group"], categories=[FACTORS["func_group"]] +
                                      sorted(set(df.func_group) - {FACTORS["func_group"]}))
    df["condition_group"] = pd.Categorical(
        df["condition_group"], categories=[FACTORS["condition_group"]] +
        sorted(set(df.condition_group) - {FACTORS["condition_group"]}))

    formula = ("z ~ C(area, Treatment(reference='V1')) "
               "+ C(band, Treatment(reference='theta')) "
               "+ C(func_group, Treatment(reference='Other')) "
               "+ C(condition_group, Treatment(reference='baseline')) "
               "+ C(subject)")
    res, why, estimator = fit_mixed(df, formula, "session")
    notes = []
    if res is None:
        raise SystemExit(f"main GLMM failed to fit: {why}")

    main_rows = coef_rows(res, "main_effects",
                           {"n_obs": int(len(df)), "n_sessions": int(df.session.nunique()),
                            "estimator": estimator})

    pw_rows = []
    for factor, levels in [("area", sorted(df.area.unique())),
                           ("band", sorted(df.band.unique())),
                           ("func_group", sorted(df.func_group.unique())),
                           ("condition_group", sorted(df.condition_group.unique()))]:
        pw_rows += pairwise_rows(res, factor, levels, "pairwise_contrasts")

    main_df = pd.DataFrame(main_rows)
    main_df["is_subject"] = main_df.term.str.startswith("C(subject)")
    testable = main_df[main_df.term != "Intercept"].copy()
    _, holm_p, _, _ = multipletests(testable.p_raw, alpha=ALPHA, method="holm")
    _, bh_p, _, _ = multipletests(testable.p_raw, alpha=ALPHA, method="fdr_bh")
    testable["holm_p"] = holm_p
    testable["bh_q"] = bh_p
    main_df = main_df.merge(testable[["term", "holm_p", "bh_q"]], on="term", how="left")

    pw_df = pd.DataFrame(pw_rows)
    _, holm_p2, _, _ = multipletests(pw_df.p_raw, alpha=ALPHA, method="holm")
    _, bh_p2, _, _ = multipletests(pw_df.p_raw, alpha=ALPHA, method="fdr_bh")
    pw_df["holm_p"] = holm_p2
    pw_df["bh_q"] = bh_p2

    main_df.to_csv(os.path.join(IN_DIR, "glmm_summary.csv"), index=False)
    pw_df.to_csv(os.path.join(IN_DIR, "glmm_pairwise.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "response": "z = (real_r - null_mean) / null_std, per (session, condition_group, "
                    "area, func_group, band)",
        "family": "Gaussian, identity link (linear mixed model)",
        "estimation": estimator, "random_effects": "random intercept for session",
        "subject_handling": "additive fixed effect (3 levels, cannot identify a random-effect "
                            "variance component) -- same convention as fig05's area GLMM",
        "reference_levels": FACTORS,
        "n_obs": int(len(df)), "n_sessions": int(df.session.nunique()),
        "multiplicity": "Holm-Bonferroni (FWER) and BH-FDR reported for two families: (1) "
                        "main-effect vs-reference coefficients, (2) all pairwise contrasts "
                        "across area/band/func_group/condition_group",
        "n_main_terms_tested": int(len(testable)), "n_pairwise_tested": int(len(pw_df)),
        "n_main_holm_sig": int((testable.holm_p < ALPHA).sum()),
        "n_pairwise_holm_sig": int((pw_df.holm_p < ALPHA).sum()),
        "notes": notes,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "pandas": pd.__version__, "statsmodels": sm.__version__,
                "platform": platform.platform()},
    }
    with open(os.path.join(IN_DIR, "glmm_results.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(main_df.to_string(index=False))
    print(f"\nmain effects: {int((testable.holm_p < ALPHA).sum())}/{len(testable)} survive Holm, "
          f"{int((testable.bh_q < ALPHA).sum())}/{len(testable)} survive BH-FDR")
    print(f"pairwise: {int((pw_df.holm_p < ALPHA).sum())}/{len(pw_df)} survive Holm, "
          f"{int((pw_df.bh_q < ALPHA).sum())}/{len(pw_df)} survive BH-FDR")
    surv = pw_df[pw_df.holm_p < ALPHA].sort_values("bh_q")
    print("\nHolm-significant pairwise contrasts:")
    print(surv.to_string(index=False) if len(surv) else "  (none)")
    print(f"\nWROTE {IN_DIR}/glmm_summary.csv, glmm_pairwise.csv, glmm_results.json")


if __name__ == "__main__":
    main()
