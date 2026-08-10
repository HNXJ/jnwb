r"""
Within-session negative-binomial rate-ratio test: does population A's firing rate at a lag
predict population B's spike count, and by how much (a rate ratio, with its own model-based
significance)? Sits ALONGSIDE extract_population_spk_spk_lag_corr.py's lead/lag correlation
(2026-08-06 direction: neither replaces the other yet) as a second, complementary way of asking
the same lead/lag question for fig06.

QUESTION (as posed): if units of area x functional-group A fire, does that raise or lower the
odds/rate of area x functional-group B firing, at some lag, and how significant is it?

WHY NEGATIVE BINOMIAL, NOT A BAYESIAN TEST OR A SHUFFLE NULL
    A literal Bayesian test (priors, posteriors, Bayes factors) would be a fourth distinct
    inferential framework in this project (already: MixedLM/REML GLMM, permutation shuffle-null,
    Clopper-Pearson) -- against this project's own doctrine to minimize the diversity of
    inferential frameworks. A mixed/fixed-effects regression giving a rate ratio with a p-value
    answers the same question ("by how much, how significant") inside the SAME kind of backbone
    already used for fig05/fig07 (a GLM), just with a Poisson-family response instead of
    Gaussian. Real population spike counts here are overdispersed (variance/mean of 1.4-8.3
    measured directly on sub-C31o_ses-230816 PFC units before committing to a model) -- plain
    Poisson standard errors would be anti-conservative. Negative-binomial regression accounts
    for that dispersion directly and gives a valid Wald p-value from ONE fit, which is also why
    this script does NOT use a trial-mismatch shuffle null the way the lead/lag correlation
    script does: at ~90,000 (pair, lag, session) cells, a 200-shuffle permutation design (as
    used for the correlation-based analysis) was estimated at ~6 hours; a single NB fit per cell
    (~3ms, benchmarked directly before building this) is entirely tractable and does not trade
    away validity to get there, since the NB model's own inference is already appropriate for
    the overdispersion actually observed.

DESIGN
    Per (session, condition_group, node pair, lag): predictor = node A's mean population rate
    (Hz, z-scored within session) in a window shifted by `lag` relative to node B's window;
    response = node B's total spike COUNT (integer, not rate) in its own FIXED window, same
    trial. Fit sm.NegativeBinomial(count_B ~ 1 + rate_A_z) using that session's own trials as
    the sample (no cross-session pooling at this stage -- pool after testing, not before, same
    as everywhere else this project tests connectivity/coupling). The coefficient on rate_A_z is
    a log rate ratio; exp(coefficient) is the rate ratio; the model's own Wald p-value on that
    coefficient is the session's test statistic.

    LAG RANGE: +-200 ms, 10 ms steps (41 lags) -- wider than the correlation-based script's
    +-100 ms, per explicit request. Each node's rate/count trace is extracted with 200 ms of
    margin on both sides so a lag-shifted predictor window never runs past extracted data.

NODES: (area10, functional_group), STABLE UNITS ONLY
    "Stable" = quality==1 (single unit) AND trial_presence_fraction > 0.98
    (STABLE_KEEP_THRESHOLD, same definition as fig03_unit_census.py's attach_stability()), from
    outputs/classification/unit_trial_presence.csv. This is a stricter unit filter than
    extract_population_firing_lfp_power_corr.py's (firing_rate >= 0.5 Hz only) -- reflects an
    explicit request for stable units only in this analysis, not a change to that script.
    Groups: S+, S-, O+, O++, Other (all five; O++ requested explicitly despite its small size --
    3 stable O++ units corpus-wide, at most 1 per area per session, meaning O++ will contribute
    zero cells at the >=2-units-per-node floor used here. Included in the code rather than
    silently dropped, so a future corpus expansion could populate it without a script change).

SCOPE
    within_area  : pairs of DIFFERENT functional groups in the SAME area
    between_area : any functional-group pair across DIFFERENT areas

OUTPUT
    outputs/population_spk_spk_rateratio_nb/<session>.csv.gz
    outputs/population_spk_spk_rateratio_nb/index.csv
    outputs/population_spk_spk_rateratio_nb/receipt.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from itertools import combinations

import numpy as np
import pandas as pd
import statsmodels.api as sm

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
sys.path.insert(0, SCRIPTS)
import jnwb as oa  # noqa: E402
from jnwb.unit_classification import precompute_condition_onsets  # noqa: E402
from jnwb.connectivity import bin_spikes  # noqa: E402
from extract_population_firing_lfp_power_corr import (  # noqa: E402
    build_functional_groups, CONDITION_GROUPS, UNITS_CSV,
)
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
PRESENCE_CSV = _P.REPO_ROOT / "outputs/classification/unit_trial_presence.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/population_spk_spk_rateratio_nb"

BIN_MS = 10.0
MAX_LAG_MS = 200.0
LAG_STEP_MS = 10.0
PAD_MS = MAX_LAG_MS
STABLE_KEEP_THRESHOLD = 0.98
MIN_UNITS_PER_GROUP = 2
FUNC_GROUPS = ("S+", "S-", "O+", "O++", "Other")


def load_stable_units():
    units = pd.read_csv(UNITS_CSV)
    units = build_functional_groups(units)
    presence = pd.read_csv(PRESENCE_CSV)
    stable_keys = set(zip(presence.loc[presence.trial_presence_fraction > STABLE_KEEP_THRESHOLD,
                                       "session"],
                          presence.loc[presence.trial_presence_fraction > STABLE_KEEP_THRESHOLD,
                                      "unit_row"]))
    is_stable = [(s, u) in stable_keys for s, u in zip(units.session, units.unit_row)]
    units["is_stable"] = np.array(is_stable) & (units.quality == 1)
    return units[units.is_stable & units.func_group.notna()].copy()


def fit_nb_rate_ratio(rate_a, count_b):
    """One NB regression, one session's trials. Returns (log_rate_ratio, se, p) or None."""
    if len(rate_a) < 15 or np.std(rate_a) == 0 or np.sum(count_b) == 0:
        return None
    x = (rate_a - rate_a.mean()) / rate_a.std()
    X = sm.add_constant(x)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = sm.NegativeBinomial(count_b, X).fit(disp=0, maxiter=100)
        coef, se, p = res.params[1], res.bse[1], res.pvalues[1]
        if not np.isfinite(coef) or not np.isfinite(p):
            return None
        return float(coef), float(se), float(p)
    except Exception:
        return None


def main(limit_sessions=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    units_df = load_stable_units()
    sessions = sorted(units_df.session.unique())
    if limit_sessions:
        sessions = sessions[:limit_sessions]
    print(f"{len(sessions)} sessions with >=1 stable, classified unit", flush=True)

    pad_bins = int(round(PAD_MS / BIN_MS))
    lag_step_bins = int(round(LAG_STEP_MS / BIN_MS))
    lags_bins = np.arange(-pad_bins, pad_bins + 1, lag_step_bins)

    index_rows = []
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        candidates = [os.path.join(NWB_DIR, f"{session}_rec.nwb"),
                     os.path.join(NWB_DIR, f"{session}.nwb")]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            continue
        try:
            sess = oa.read(path)
        except Exception:
            continue
        onsets = precompute_condition_onsets(sess, correct_only=True)
        sess_units = units_df[units_df.session == session]

        rows_out = []
        for cg_name, (cond, win_ms) in CONDITION_GROUPS.items():
            trial_starts = onsets.get(cond, np.array([]))
            if len(trial_starts) < 15:
                continue
            win_len_core = int(round((win_ms[1] - win_ms[0]) / BIN_MS))
            padded_win_s = ((win_ms[0] - PAD_MS) / 1000.0, (win_ms[1] + PAD_MS) / 1000.0)

            rates, counts = {}, {}
            for area, garea in sess_units.groupby("area10"):
                for fgroup, gfg in garea.groupby("func_group"):
                    if fgroup not in FUNC_GROUPS or len(gfg) < MIN_UNITS_PER_GROUP:
                        continue
                    unit_rate_traces, unit_count_traces = [], []
                    for unit_row in gfg.unit_row:
                        try:
                            st = sess.get_spike_times(int(unit_row))
                        except Exception:
                            continue
                        if st is None or len(st) == 0:
                            continue
                        r = bin_spikes(st, window=padded_win_s, bin_size_ms=BIN_MS,
                                      trial_starts=trial_starts, output="rate")
                        c = bin_spikes(st, window=padded_win_s, bin_size_ms=BIN_MS,
                                      trial_starts=trial_starts, output="count")
                        unit_rate_traces.append(r)
                        unit_count_traces.append(c)
                    if len(unit_rate_traces) < MIN_UNITS_PER_GROUP:
                        continue
                    n_tr = min(t.shape[0] for t in unit_rate_traces)
                    n_bins = min(t.shape[1] for t in unit_rate_traces)
                    rates[(area, fgroup)] = np.nanmean(
                        np.stack([t[:n_tr, :n_bins] for t in unit_rate_traces]), axis=0)
                    counts[(area, fgroup)] = np.sum(
                        np.stack([t[:n_tr, :n_bins] for t in unit_count_traces]), axis=0)

            nodes = list(rates)
            pairs = []
            for n1, n2 in combinations(nodes, 2):
                if n1[0] == n2[0] and n1[1] == n2[1]:
                    continue
                scope = "within_area" if n1[0] == n2[0] else "between_area"
                pairs.append((scope, n1, n2))

            exp_len = win_len_core + 2 * pad_bins
            for scope, n1, n2 in pairs:
                x_rate, y_count = rates[n1], counts[n2]
                n_tr = min(x_rate.shape[0], y_count.shape[0])
                if x_rate.shape[1] < exp_len or y_count.shape[1] < exp_len or n_tr < 15:
                    continue
                y_core = y_count[:n_tr, pad_bins:pad_bins + win_len_core].sum(axis=1)
                for lag_bins in lags_bins:
                    a0 = pad_bins + lag_bins
                    x_lagged = x_rate[:n_tr, a0:a0 + win_len_core].mean(axis=1)
                    fit = fit_nb_rate_ratio(x_lagged, y_core)
                    if fit is None:
                        continue
                    coef, se, p = fit
                    rows_out.append({
                        "condition_group": cg_name, "scope": scope,
                        "node1_area": n1[0], "node1_func": n1[1],
                        "node2_area": n2[0], "node2_func": n2[1],
                        "lag_ms": float(lag_bins * BIN_MS), "n_trials": int(n_tr),
                        "log_rate_ratio": coef, "rate_ratio": float(np.exp(coef)),
                        "se": se, "p": p,
                    })

        if not rows_out:
            continue
        out_df = pd.DataFrame(rows_out)
        out_df.to_csv(os.path.join(OUT_DIR, f"{session}.csv.gz"), index=False)
        index_rows.append({"session": session, "n_rows": len(out_df)})
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{len(out_df)} (pair,lag,cg) fits, {time.time()-t0:.0f}s total", flush=True)

    pd.DataFrame(index_rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Within-session negative-binomial rate-ratio test between (area, "
                  "func_group) population nodes, across a +-200ms lag axis -- sits ALONGSIDE "
                  "extract_population_spk_spk_lag_corr.py's correlation-based lead/lag test "
                  "for fig06, does not replace it (2026-08-06 direction).",
        "model": "sm.NegativeBinomial(count_B ~ 1 + z(rate_A_at_lag)), one fit per "
                "(session, condition_group, pair, lag), Wald p-value on the rate_A coefficient",
        "why_not_poisson": "measured overdispersion (variance/mean 1.4-8.3) on real PFC unit "
                          "spike counts before choosing NB over Poisson",
        "why_not_shuffle_null": "estimated ~6h for a 200-shuffle permutation design at this "
                               "cell count (~90,000 fits); NB's own Wald test is valid given "
                               "the measured overdispersion and needs one fit per cell (~3ms)",
        "nodes": "(area10, func_group in S+/S-/O+/O++/Other), STABLE units only "
                "(quality==1 & trial_presence_fraction>0.98)",
        "condition_groups": {k: {"nwb_condition": v[0], "window_ms_re_p1": list(v[1])}
                             for k, v in CONDITION_GROUPS.items()},
        "lag_range_ms": [-MAX_LAG_MS, MAX_LAG_MS], "lag_step_ms": LAG_STEP_MS,
        "pad_ms_each_side": PAD_MS, "bin_ms": BIN_MS,
        "min_units_per_group": MIN_UNITS_PER_GROUP,
        "predictor_response_convention": "predictor = node1's rate at the given lag; "
                                        "response = node2's spike count in its own fixed "
                                        "window; positive lag shifts node1's window LATER",
        "n_sessions_processed": len(index_rows),
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/ ({len(index_rows)} sessions), index.csv, receipt.json")


if __name__ == "__main__":
    main(limit_sessions=int(sys.argv[1]) if len(sys.argv) > 1 else None)
