r"""
Generalization of fig04_v1_pfc_condition_tfr.py's two retained GLMMs (fit_omission_yesno_glmm,
fit_omission_type_glmm) to (1) all 10 canonical analysis areas, not just the 4-area main-figure
subset (CONDITION_AREAS) plus the separately-drawn 6-area supplement subset (SUPP_AREAS), and
(2) a time-resolved p2 window instead of one collapsed scalar per session x area x band x
condition.

WRITTEN AS A NEW FILE, NOT AN EDIT TO fig04_v1_pfc_condition_tfr.py
    Per this project's CLAUDE.md working agreement ("Preserve originals; write revisions as new
    files") and "change only what the task requires": fig04_v1_pfc_condition_tfr.py is a live
    manuscript figure script (draws fig04.svg + supplements). Splitting its area universe across
    CONDITION_AREAS/SUPP_AREAS is a DRAWING-layout decision (main figure vs supplement panel
    count), not a statistical one -- merging them for the GLMM does not require touching the
    figure-drawing code at all. This script imports the reusable pieces (load_condition_maps,
    area_cond_sessions, band_ratio, to_db, GLMM_CONDS/COND_CONTEXT/COND_FAMILY,
    GLMM_MIN_SESSIONS/GLMM_MIN_ANIMALS) rather than duplicating them, and adds only the
    generalization: all 10 areas (figstyle.AREA_ORDER) in one loop, and a `window` level in the
    (area, band) groupby of both retained models.

DOES NOT RESURRECT THE RETIRED context x family INTERACTION MODEL
    Per fig04_v1_pfc_condition_tfr.py's own docstring (2026-08-04 reframe, lines ~577-585): that
    design answered "does the SIZE of the stimulus-vs-omission gap depend on family" and was
    retired in favor of exactly the two models generalized here: Q1 "is it an omission at all"
    (fit_omission_yesno_glmm, db ~ C(context)) and Q2 "among omissions, does predictability
    matter" (fit_omission_type_glmm, db ~ C(family), omission rows only). Both retained.

TIME-RESOLVED WINDOW, DECISION RECORDED
    P2_WINDOW_MS = (1031, 1562), 531 ms wide. Chosen bin width: 150 ms -> 4 bins (150, 150,
    150, 81 ms; the last bin is short because 531 is not a multiple of 150 -- kept rather than
    dropped or padded, since the coverage gate downstream already tolerates partial bins via
    np.any(np.isfinite(...))). 150 ms is a compromise stated explicitly, not tuned per result:
    narrow enough to say something about WHEN within the omission window an effect appears
    (finer than the single collapsed scalar the original model used), wide enough that each
    bin still averages over several of the TFR's own native 10 ms time bins (15 native bins per
    150 ms bin) and keeps the (area x band x window) test family at a tractable size --
    10 areas x 5 bands x 4 windows = 200 tests per model, comparable in order of magnitude to
    fig05's own 45- and 225-test families elsewhere in this project, not a combinatorial blowup.

DECLARED FAMILIES (new, window-inclusive -- NOT the same family as the original scalar model)
    fig04_glmm_is_omission_timeresolved  (Q1, 10 areas x 5 bands x 4 windows = up to 200 tests)
    fig04_glmm_omission_type_timeresolved (Q2, same grid)
    These are declared explicitly here as their own families, separate from
    fig04_glmm_is_omission / fig04_glmm_omission_type (the original single-window family in
    fig04_v1_pfc_condition_tfr.py) -- per this project's multiplicity rule, adding a window
    level is a different, larger family and must not be silently merged with or silently
    replace the narrower one.

OUTPUT
    outputs/fig04_glmm_all_areas_timeresolved/glmm_timeresolved_stats.csv (via figstats.write)
    outputs/fig04_glmm_all_areas_timeresolved/glmm_timeresolved_stats.md
    artifacts/.lab/fig04-glmm-all-areas-timeresolved-20260813.json (decision receipt)
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FIGDIR))
sys.path.insert(0, FIGDIR)
sys.path.insert(0, HERE)

from figstats import Result, correct, write  # noqa: E402
from figstyle import AREA_ORDER  # noqa: E402
import fig04_v1_pfc_condition_tfr as _fig04  # noqa: E402
from fig04_v1_pfc_condition_tfr import (  # noqa: E402
    load_condition_maps, area_cond_sessions, band_ratio, to_db,
    GLMM_CONDS, COND_CONTEXT, COND_FAMILY, GLMM_MIN_SESSIONS, GLMM_MIN_ANIMALS,
    BANDSETS,
)

# fig04_v1_pfc_condition_tfr.py hardcodes CONDITION_MAPS to a stale absolute path
# ("D:/workspace/omission/outputs/..."); this repo actually resolves to a different root
# (jnwb.paths.REPO_ROOT / the CLAUDE.md-documented "drive remap" footgun -- same class of bug
# omission-data skill warns about for hardcoded external roots). The file itself exists at the
# correct repo-relative location (outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz); patch the
# module-level constant here (not the original file, per "preserve originals, write revisions
# as new files") before calling load_condition_maps().
_fig04.CONDITION_MAPS = os.path.join(REPO, "outputs", "condition_tfr_maps_p1d1p2d2p3", "maps.npz")

P2_WINDOW_MS = (1031.0, 1562.0)
WINDOW_BIN_MS = 150.0
OUT_DIR = os.path.join(REPO, "outputs", "fig04_glmm_all_areas_timeresolved")


def time_windows():
    """(label, lo_ms, hi_ms) tuples covering P2_WINDOW_MS in WINDOW_BIN_MS steps -- the last
    bin is short (531 % 150 = 81 ms) rather than dropped or padded; see module docstring."""
    lo0, hi0 = P2_WINDOW_MS
    edges = list(np.arange(lo0, hi0, WINDOW_BIN_MS)) + [hi0]
    out = []
    for i in range(len(edges) - 1):
        out.append((f"w{i}_{int(edges[i])}-{int(edges[i+1])}ms", edges[i], edges[i + 1]))
    return out


def build_glmm_long_table_timeresolved(maps, freqs, times, bands):
    """Same per-row construction as fig04_v1_pfc_condition_tfr.py::build_glmm_long_table, but
    (a) all 10 AREA_ORDER areas instead of CONDITION_AREAS alone, and (b) one row per time
    window instead of one row for the whole P2_WINDOW_MS span."""
    windows = time_windows()
    rows = []
    for area in AREA_ORDER:
        for cond in GLMM_CONDS:
            sess = area_cond_sessions(maps, area, cond)
            for sname, m in sess.items():
                animal = sname.split("_ses-")[0].replace("sub-", "")
                for band, (lo, hi) in bands.items():
                    for wlabel, wlo, whi in windows:
                        tmask = (times >= wlo) & (times < whi)
                        r = band_ratio(m, freqs, lo, hi)[tmask]
                        if not np.any(np.isfinite(r)):
                            continue
                        rows.append({
                            "area": area, "band": band, "window": wlabel,
                            "session": sname, "animal": animal, "cond": cond,
                            "context": COND_CONTEXT[cond], "family": COND_FAMILY[cond],
                            "db": to_db(np.nanmean(r)),
                        })
    return pd.DataFrame(rows)


def fit_omission_yesno_glmm_timeresolved(df_long):
    """Q1, time-resolved: db ~ C(context), grouped by (area, band, window) instead of
    (area, band) alone. Same model spec, random-effects structure, and reference-level
    assertion as fit_omission_yesno_glmm -- only the groupby key changed."""
    import statsmodels.formula.api as smf

    results, convergence_notes = [], []
    for (area, band, window), g in df_long.groupby(["area", "band", "window"]):
        g = g.dropna(subset=["db"])
        n_sessions, n_animals = g.session.nunique(), g.animal.nunique()
        if n_sessions < GLMM_MIN_SESSIONS or n_animals < GLMM_MIN_ANIMALS:
            continue
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            try:
                m = smf.mixedlm("db ~ C(context)", g, groups=g["animal"],
                                vc_formula={"session": "0 + C(session)"}).fit(reml=False)
            except Exception as e:
                convergence_notes.append(f"{area} {band} {window}: fit failed -- {e}")
                continue
            if wlist:
                convergence_notes.append(f"{area} {band} {window}: " +
                                         "; ".join(str(w.message) for w in wlist))

        ctx_terms = [t for t in m.params.index if t.startswith("C(context)")]
        if not ctx_terms:
            continue
        t = ctx_terms[0]
        assert t == "C(context)[T.stimulus]", (
            f"unexpected patsy reference level for context: {t!r}")
        coef, se, p = float(m.params[t]), float(m.bse[t]), float(m.pvalues[t])
        results.append(Result(
            figure="fig04_glmm_timeresolved", panel="glmm_yesno",
            question=f"{area} {band} {window}: is it an omission? (stimulus vs omission, "
            "pooled family)",
            test="LMM Wald (statsmodels mixedlm, ML)", statistic_name="z",
            statistic=coef / se if se > 0 else np.nan, df="", n=n_sessions, unit="session",
            effect_name="context coef (dB, stimulus-omission)", effect=coef, p=p,
            family="fig04_glmm_is_omission_timeresolved",
            note=f"{n_animals} animals; window={window}; positive = more power for real "
                 "stimulus than omission, same sign convention as the original scalar model"))

    return results, convergence_notes


def fit_omission_type_glmm_timeresolved(df_long):
    """Q2, time-resolved: db ~ C(family), omission-context rows only, grouped by
    (area, band, window). Same likelihood-ratio-vs-intercept-only design as
    fit_omission_type_glmm, window added to the groupby key."""
    import statsmodels.formula.api as smf
    from scipy.stats import chi2

    omitted = df_long[df_long.context == "omission"]
    results, convergence_notes = [], []
    for (area, band, window), g in omitted.groupby(["area", "band", "window"]):
        g = g.dropna(subset=["db"])
        n_sessions, n_animals = g.session.nunique(), g.animal.nunique()
        if n_sessions < GLMM_MIN_SESSIONS or n_animals < GLMM_MIN_ANIMALS:
            continue
        vc = {"session": "0 + C(session)"}
        with warnings.catch_warnings(record=True) as wlist:
            warnings.simplefilter("always")
            try:
                m_null = smf.mixedlm("db ~ 1", g, groups=g["animal"], vc_formula=vc).fit(reml=False)
                m_full = smf.mixedlm("db ~ C(family)", g, groups=g["animal"],
                                     vc_formula=vc).fit(reml=False)
            except Exception as e:
                convergence_notes.append(f"{area} {band} {window} (omission type): fit "
                                        f"failed -- {e}")
                continue
            if wlist:
                convergence_notes.append(f"{area} {band} {window} (omission type): " +
                                         "; ".join(str(w.message) for w in wlist))

        lr = 2.0 * (m_full.llf - m_null.llf)
        df_diff = int(m_full.model.k_fe - m_null.model.k_fe)
        p_lr = float(chi2.sf(max(lr, 0.0), df_diff)) if df_diff > 0 else np.nan
        results.append(Result(
            figure="fig04_glmm_timeresolved", panel="glmm_type",
            question=f"{area} {band} {window}: does omission type matter (predictable A/B "
            "vs unpredictable R)?",
            test="LMM likelihood-ratio (db~C(family) vs db~1)", statistic_name="LR chi2",
            statistic=float(lr), df=str(df_diff), n=n_sessions, unit="session",
            p=p_lr, family="fig04_glmm_omission_type_timeresolved",
            note=f"{n_animals} animals; window={window}; omission-only rows "
                 "(RXRR/AXAB/BXBA); session-nested random effects, ML"))

    return results, convergence_notes


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    maps, count_maps, freqs, times = load_condition_maps()
    bands = BANDSETS["manuscript"]

    df_long = build_glmm_long_table_timeresolved(maps, freqs, times, bands)
    print(f"long table: {len(df_long)} rows, areas={sorted(df_long.area.unique())}, "
         f"windows={sorted(df_long.window.unique())}")

    r1, notes1 = fit_omission_yesno_glmm_timeresolved(df_long)
    r2, notes2 = fit_omission_type_glmm_timeresolved(df_long)
    print(f"Q1 (is it an omission?): {len(r1)} cells fit, {len(notes1)} convergence notes")
    print(f"Q2 (omission type): {len(r2)} cells fit, {len(notes2)} convergence notes")

    all_results = r1 + r2
    correct(all_results)   # BH + Holm within each declared family, in place

    write(all_results, OUT_DIR, "glmm_timeresolved",
         title="fig04 GLMM generalization -- all 10 areas, time-resolved p2 window",
         preamble=f"Generalizes fig04_v1_pfc_condition_tfr.py's two retained models "
                  f"(Q1 is-it-an-omission, Q2 omission-type) from 4+6-area split-path "
                  f"coverage to all 10 AREA_ORDER areas in one loop, and from one collapsed "
                  f"P2_WINDOW_MS scalar to {len(time_windows())} time bins "
                  f"({WINDOW_BIN_MS:.0f} ms each) spanning {P2_WINDOW_MS}. Does NOT include "
                  f"the retired context x family interaction design. Two new declared "
                  f"families: fig04_glmm_is_omission_timeresolved, "
                  f"fig04_glmm_omission_type_timeresolved -- separate from the original "
                  f"single-window families of the same name minus '_timeresolved'.")

    n_holm_q1 = sum(1 for r in r1 if np.isfinite(r.p_holm) and r.p_holm < 0.05)
    n_bh_q1 = sum(1 for r in r1 if np.isfinite(r.q_bh) and r.q_bh < 0.05)
    n_holm_q2 = sum(1 for r in r2 if np.isfinite(r.p_holm) and r.p_holm < 0.05)
    n_bh_q2 = sum(1 for r in r2 if np.isfinite(r.q_bh) and r.q_bh < 0.05)
    print(f"Q1: {n_holm_q1}/{len(r1)} Holm-significant, {n_bh_q1}/{len(r1)} BH-significant")
    print(f"Q2: {n_holm_q2}/{len(r2)} Holm-significant, {n_bh_q2}/{len(r2)} BH-significant")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "areas": AREA_ORDER, "n_areas": len(AREA_ORDER),
        "window_bin_ms": WINDOW_BIN_MS, "p2_window_ms": list(P2_WINDOW_MS),
        "windows": [w[0] for w in time_windows()],
        "glmm_min_sessions": GLMM_MIN_SESSIONS, "glmm_min_animals": GLMM_MIN_ANIMALS,
        "q1_n_tested": len(r1), "q1_n_holm_sig": n_holm_q1, "q1_n_bh_sig": n_bh_q1,
        "q2_n_tested": len(r2), "q2_n_holm_sig": n_holm_q2, "q2_n_bh_sig": n_bh_q2,
        "convergence_notes_q1": notes1[:50], "convergence_notes_q2": notes2[:50],
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"WROTE {OUT_DIR}/")


if __name__ == "__main__":
    main()
