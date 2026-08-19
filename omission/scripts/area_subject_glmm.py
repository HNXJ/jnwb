r"""
Shared area x subject additive GLMM (+ all pairwise area contrasts) -- used by both
fit_omission_band_power_glmm.py (omission-window response) and fit_stim_band_power_glmm.py
(stimulus-window response), so the two censuses are analyzed with byte-identical logic instead
of two independently-maintained copies that can silently drift apart. This project has already
found two real bugs from exactly that kind of duplication once this session (an incomplete area
pooling dict and an inverted-rank BH correction, both in fit_omission_band_power_glmm.py before
2026-08-05) -- this module exists specifically to not repeat that pattern for the stimulus side.

MODEL
    db ~ C(area, Treatment(ref_area)) + C(subject), session-level (one row per session x area,
    avoiding channel-level pseudo-replication), session as the MixedLM random-intercept group.
    Subject is an explicit ADDITIVE fixed effect. Identifiable as long as the area x subject
    design is connected (every area recorded in >=2 subjects) -- true for both the omission and
    stimulus censuses, since both draw areas from the same recording sessions.

    MixedLM (REML) is tried first; falls back to OLS with session-cluster-robust SEs if MixedLM
    hits a singular matrix (happens when the between-session variance component becomes
    non-identifiable once area+subject fixed effects already absorb most of the structure --
    observed for some bands, not others, data-dependent). Which estimator produced a given row
    is always recorded, never hidden.

PAIRWISE CONTRASTS
    The single fitted model already contains every pairwise area difference as a linear
    combination of its own coefficients -- coef(A) - coef(B) for two non-reference areas, or
    coef(A) alone for A vs the reference -- with a correctly propagated SE via
    res.t_test(contrast). Computed for the full C(n_areas, 2) grid from one fit per band, not
    by refitting per pair.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.regression.mixed_linear_model import MixedLM

from jnwb.statistics import coef_rows  # noqa: F401 (re-exported for existing importers)


def fit_mixed(d: pd.DataFrame, formula: str, group: str):
    """REML fit; returns (result, None) or (None, reason)."""
    d = d.dropna(subset=[group])
    if d[group].nunique() < 3 or len(d) < 20:
        return None, f"only {d[group].nunique()} groups / {len(d)} obs"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            md = MixedLM.from_formula(formula, groups=d[group], data=d)
            res = md.fit(reml=True, method="lbfgs")
        return res, None
    except Exception as e:
        return None, f"fit failed: {type(e).__name__}: {e}"




def fit_area_subject_and_pairwise(df, resp, bands, ref_area, model_name, pairwise_model_name):
    """df must have columns: session_prefix, area_infer, subject, band, <resp>.

    Returns (rows, notes) -- rows include both the vs-reference coefficients (model_name) and
    every pairwise area contrast (pairwise_model_name), for every band.
    """
    rows, notes = [], []
    for b in bands:
        saf = (df[df.band == b]
              .groupby(["session_prefix", "area_infer", "subject"], as_index=False)[resp].mean())
        saf["area"] = pd.Categorical(saf["area_infer"],
                                     categories=[ref_area] + sorted(set(saf.area_infer) - {ref_area}))
        formula = f"{resp} ~ C(area, Treatment(reference='{ref_area}')) + C(subject)"
        res, why = fit_mixed(saf, formula, "session_prefix")
        estimator = "MixedLM_REML"
        if res is None:
            try:
                res = smf.ols(formula, data=saf).fit(
                    cov_type="cluster", cov_kwds={"groups": saf["session_prefix"]})
                estimator = "OLS_cluster_robust_by_session"
            except Exception as e:
                notes.append(f"{model_name}/{b}: MixedLM failed ({why}); "
                             f"OLS fallback also failed: {e}")
                continue
        rows += coef_rows(res, model_name, b,
                          {"reference_area": ref_area, "n_obs": int(len(saf)),
                           "n_sessions": int(saf.session_prefix.nunique()),
                           "estimator": estimator})

        areas_all = [ref_area] + [c for c in saf["area"].cat.categories if c != ref_area]
        exog_names = list(res.model.exog_names)
        area_col = {}
        for name in exog_names:
            for a in areas_all[1:]:
                if name.endswith(f"[T.{a}]") and name.startswith("C(area"):
                    area_col[a] = name
        for i, a in enumerate(areas_all):
            for bb in areas_all[i + 1:]:
                # term label below is f"{bb} - {a}" -- contrast must compute coef(bb)-coef(a)
                # to match: +1 on bb's column, -1 on a's column (reference area contributes 0,
                # its coefficient is the baseline). Getting this backwards was a real bug caught
                # 2026-08-05 by a sign sanity check against Model F's own vs-reference
                # coefficients before trusting a rendered pairwise-matrix figure.
                contrast = np.zeros((1, len(exog_names)))
                if bb != ref_area:
                    contrast[0, exog_names.index(area_col[bb])] += 1.0
                if a != ref_area:
                    contrast[0, exog_names.index(area_col[a])] -= 1.0
                if not np.any(contrast):
                    continue
                try:
                    tt = res.t_test(contrast)
                except Exception as e:
                    notes.append(f"{pairwise_model_name}/{b}/{a}-{bb}: t_test failed: {e}")
                    continue
                ci = np.ravel(tt.conf_int())
                rows.append({
                    "model": pairwise_model_name, "band": b, "term": f"{bb} - {a}",
                    "estimate_db": float(np.ravel(tt.effect)[0]),
                    "se": float(np.ravel(tt.sd)[0]), "z": float(np.ravel(tt.tvalue)[0]),
                    "p_raw": float(np.ravel(tt.pvalue)[0]),
                    "ci_lo": float(ci[0]), "ci_hi": float(ci[1]),
                    "reference_area": None, "n_obs": int(len(saf)),
                    "n_sessions": int(saf.session_prefix.nunique()), "estimator": estimator,
                })
    return rows, notes
