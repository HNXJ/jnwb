r"""
Continuous-time onset-of-divergence estimate for LFP band power (real stimulus vs omitted p2
slot), at the TFR corpus's native 10ms resolution -- replaces the discrete 150ms-binned GLMM
window table (outputs/fig04_glmm_all_areas_timeresolved_v3/onset_of_significance_by_area_band.csv)
with a continuous onset fit, per Hamm's direct correction (2026-08-15): "no delay between task
event and neural signal can be less than 10ms ... temporal resolution should be up to 5ms error."

WHY THIS EXISTS, NOT A NEW EXTRACTION
    scripts/precompute_tfr_arrays.py's (renamed 2026-08-22 from precompute_tfr_arrays_v2.py) own
    BIN_MS=10.0 shows the TFR array feeding fig04's
    v3 GLMM (outputs/condition_tfr_maps_p1d1p2d2p3_v3/maps.npz, artifact-repaired, already
    accepted -- "so keep this as for fig04") is natively 10ms resolution; the GLMM script pools
    it into 150ms bins for statistical power/family-size reasons, not because finer data doesn't
    exist. True 5ms resolution would need a new spectrogram extraction (finer STFT hop) -- out
    of scope this pass per direct instruction ("redo at native 10ms resolution now").

METHOD
    Reuses omission.jnwb_ext.onset_fitting.fit_exponential_onset (already built and synthetic-validated for
    the spiking onset-hierarchy task) on a continuous LFP divergence trace instead of a spike
    rate: per session x area x band, pool the 3 within-context conditions
    (COND_CONTEXT/GLMM_CONDS from fig04_v1_pfc_condition_tfr.py -- reused, not re-derived) into
    one "stimulus" and one "omission" band-power-ratio trace, take
    diff_db(t) = to_db(ratio_stimulus(t)) - to_db(ratio_omission(t)), causally smooth
    (tau_ms=30, project convention), and fit the onset of |diff_db(t)| rising from its pre-p2
    baseline (t=0 at p2 onset, 1031ms in the maps' own p1-aligned time axis). t0 is bounded to
    [0, 600]ms post p2-onset by construction (same causality-by-construction design as the
    spiking module) -- cannot report a pre-event onset.

    Session = unit of inference (project convention); bootstrap CI on t0 across sessions per
    area x band, same pattern as fit_class_onset_latency.py's bootstrap_area_class.

PHYSICAL PLAUSIBILITY GATES (both checked, not conflated -- Hamm's 2026-08-15 decision)
    - GENERAL_MIN_LATENCY_MS = 10.0: any neural signal following any event needs >=10ms
      (synaptic + conduction delay floor). A group onset CI whose upper bound sits below this
      is flagged as implausible outright.
    - VISUAL_MIN_LATENCY_MS = 40.0: stricter, visual-stimulus-response-specific floor (existing
      project constant, scripts/fit_class_onset_latency.py). Reported alongside, not enforced
      as a hard violation here, since Q1's "is it an omission" context effect is not purely a
      sensory-onset test (see fig04-v3's own note: a predictive/expectation signal could
      legitimately precede a purely sensory response).

OUTPUT: outputs/classification/lfp_band_onset_latency/{cell_fits.csv, area_band_summary.csv}
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "context" / "figures"))
sys.path.insert(0, str(REPO / "context" / "figures" / "fig06_v1_pfc_condition_tfr"))

from omission.jnwb_ext.onset_fitting import causal_exp_smooth, fit_exponential_onset  # noqa: E402
import figstyle  # noqa: E402
from fig04_v1_pfc_condition_tfr import (  # noqa: E402
    GLMM_CONDS, COND_CONTEXT, band_ratio, to_db,
)

CONDITION_MAPS_V3 = REPO / "outputs/condition_tfr_maps_p1d1p2d2p3_v3/maps.npz"
OUT_DIR = REPO / "outputs/classification/lfp_band_onset_latency"
COVERAGE_MIN = 0.5   # same threshold fig04_v1_pfc_condition_tfr.load_condition_maps uses

P2_ONSET_MS = 1031.0          # omission.jnwb_ext.sequence_layout.EPOCH_ONSETS_MS["p2"]
FIT_WIN_MS = (P2_ONSET_MS - 100.0, P2_ONSET_MS + 600.0)
BASELINE_MS = (P2_ONSET_MS - 100.0, P2_ONSET_MS)   # pre-p2 -- identical trial history in both
                                                     # contexts up to this point, so a flat
                                                     # near-zero diff here is the correct prior
TAU_SMOOTH_MS = 30.0          # project convention (omission-figures skill)
GENERAL_MIN_LATENCY_MS = 10.0
VISUAL_MIN_LATENCY_MS = 40.0
MIN_R2 = 0.3
MIN_SESSIONS = 5
N_BOOT = 1000
SEED = 9200


def load_maps_v3():
    """Same loader logic as fig04_v1_pfc_condition_tfr.load_condition_maps(), pointed at the
    v3 (artifact-repaired, current-corpus) product instead of that module's own hardcoded
    (stale) CONDITION_MAPS path -- reimplemented locally rather than monkeypatching the
    imported module's global, since load_condition_maps() closes over that global directly."""
    z = np.load(CONDITION_MAPS_V3, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
        per_bin = np.nanmax(counts[i], axis=0)
        mx = np.nanmax(per_bin) if per_bin.size else 0
        keep = per_bin >= COVERAGE_MIN * mx if mx > 0 else per_bin > 0
        m[:, ~keep] = np.nan
        maps[k] = m
    return maps, freqs, times


def area_cond_sessions(maps, area, cond, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer and k.split("|")[3] == cond}


def context_trace(maps, area, context, session, freqs, lo, hi):
    """Mean band ratio across the within-context GLMM_CONDS for one session, or None if that
    session has no coverage for any condition in this context."""
    conds = [c for c in GLMM_CONDS if COND_CONTEXT[c] == context]
    traces = []
    for c in conds:
        sess = area_cond_sessions(maps, area, c)
        if session in sess:
            traces.append(band_ratio(sess[session], freqs, lo, hi))
    if not traces:
        return None
    return np.nanmean(np.stack(traces), axis=0)


def fit_one_cell(times, diff_db):
    tmask = (times >= FIT_WIN_MS[0]) & (times < FIT_WIN_MS[1])
    t_rel = times[tmask] - P2_ONSET_MS
    y = np.abs(diff_db[tmask])
    if not np.any(np.isfinite(y)) or np.sum(np.isfinite(y)) < 8:
        return None
    y = np.nan_to_num(y, nan=0.0)
    bin_ms = float(np.median(np.diff(times)))
    y_smooth = causal_exp_smooth(y, bin_ms, tau_ms=TAU_SMOOTH_MS)
    fit = fit_exponential_onset(
        t_rel, y_smooth, t0_bounds=(0.0, 600.0),
        baseline_window=(BASELINE_MS[0] - P2_ONSET_MS, BASELINE_MS[1] - P2_ONSET_MS),
    )
    return fit


def bootstrap_area_band(df_cell, area, band, rng):
    raw = df_cell[(df_cell.area == area) & (df_cell.band == band)]
    sub = raw[(raw.r2 >= MIN_R2) & (raw.converged)]
    n = sub.shape[0]
    if n < MIN_SESSIONS:
        return None
    onsets = sub.t0.to_numpy()
    boot = rng.choice(onsets, size=(N_BOOT, n), replace=True).mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    mean_t0 = float(onsets.mean())
    return {
        "area": area, "band": band, "n_sessions": int(n),
        "n_sessions_total": int(raw.shape[0]),
        "n_sessions_excluded_low_r2": int(raw.shape[0] - n),
        "onset_ms": mean_t0, "ci_lo_ms": float(lo), "ci_hi_ms": float(hi),
        "violates_general_10ms_floor": bool(hi < GENERAL_MIN_LATENCY_MS),
        "below_visual_40ms_floor": bool(hi < VISUAL_MIN_LATENCY_MS),
    }


def main(limit_sessions=None):
    t_start = time.time()
    maps, freqs, times = load_maps_v3()
    all_sessions = sorted({k.split("|")[0] for k in maps})
    if limit_sessions:
        all_sessions = all_sessions[:limit_sessions]

    rows = []
    for area in figstyle.AREA_ORDER:
        for band_name, (lo, hi) in figstyle.BANDS.items():
            for session in all_sessions:
                stim = context_trace(maps, area, "stimulus", session, freqs, lo, hi)
                omit = context_trace(maps, area, "omission", session, freqs, lo, hi)
                if stim is None or omit is None:
                    continue
                diff_db = to_db(stim) - to_db(omit)
                fit = fit_one_cell(times, diff_db)
                if fit is None:
                    continue
                rows.append({"area": area, "band": band_name, "session": session, **fit})
        print(f"{area}: {len(rows)} cumulative cell fits, {time.time() - t_start:.0f}s", flush=True)

    df_cell = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_cell.to_csv(OUT_DIR / "cell_fits.csv", index=False)

    rng = np.random.default_rng(SEED)
    summary_rows = []
    for area in figstyle.AREA_ORDER:
        for band_name in figstyle.BANDS:
            r = bootstrap_area_band(df_cell, area, band_name, rng)
            if r is not None:
                summary_rows.append(r)
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(OUT_DIR / "area_band_summary.csv", index=False)

    n_violate = int(df_summary.violates_general_10ms_floor.sum()) if len(df_summary) else 0
    print(f"WROTE {OUT_DIR} ({len(df_cell)} cell fits, {len(df_summary)} area x band cells, "
          f"{n_violate} violating the {GENERAL_MIN_LATENCY_MS}ms general floor, "
          f"{time.time() - t_start:.0f}s)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-sessions", type=int, default=None)
    args = ap.parse_args()
    main(limit_sessions=args.limit_sessions)
