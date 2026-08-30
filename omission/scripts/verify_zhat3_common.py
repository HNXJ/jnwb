"""INDEPENDENT VERIFICATION helpers (2026-08-28) for the Zhat-3 negative-conclusion audit.

Deliberately re-implements, from scratch, the pieces the original benchmark used, so that a
reproduction is not merely a re-run of the same code path:

  * `indep_features`      -- trial-level feature construction written directly from the window
                             definitions (no call into build_trial_level_dataset).
  * `indep_timing_hat`    -- cross-fit matched-filter timing estimate with MY OWN fold split
                             (10-fold, different seed) and a vectorised correlation, not the
                             per-shift np.roll loop.
  * `indep_delta`         -- held-out Delta = R2(M3) - R2(M2) using 10-fold CV, ORDINARY LEAST
                             SQUARES via numpy.linalg.lstsq (no Ridge, no StandardScaler, no
                             sklearn at all), returning per-row held-out predictions so a
                             bootstrap CI can be formed.
  * `clopper_pearson`     -- exact binomial interval (omission-statistics requires exact
                             intervals for proportions; no RNG, no resample count).

Nothing here imports the original distributed_lag_model estimator; callers that want the
original code path import it themselves so the two can be compared side by side.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import beta as _beta_dist

BASELINE_WINDOW = (0, 80)
HISTORY_WINDOW = (180, 205)
RESPONSE_WINDOW = (210, 230)
LAG_BINS = ((130, 150), (150, 170), (170, 190), (190, 210))


# ---------------------------------------------------------------------------------------------
# exact binomial interval
# ---------------------------------------------------------------------------------------------
def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Clopper-Pearson) two-sided 100(1-alpha)% interval for a binomial proportion."""
    lo = 0.0 if k == 0 else float(_beta_dist.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta_dist.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


# ---------------------------------------------------------------------------------------------
# independent feature construction
# ---------------------------------------------------------------------------------------------
def indep_features(P: np.ndarray, R: np.ndarray) -> dict:
    lo_b, hi_b = BASELINE_WINDOW
    lo_h, hi_h = HISTORY_WINDOW
    lo_r, hi_r = RESPONSE_WINDOW
    return {
        "outcome": R[:, lo_r:hi_r].mean(axis=1),
        "own_history": R[:, lo_h:hi_h].mean(axis=1),
        "amplitude": P[:, lo_b:hi_b].mean(axis=1),
        "lag_features": np.column_stack([P[:, lo:hi].mean(axis=1) for lo, hi in LAG_BINS]),
    }


def _my_folds(n: int, n_folds: int, seed: int) -> np.ndarray:
    """Own fold assignment: shuffle indices with a fresh Generator, then deal round-robin.
    Deliberately NOT sklearn.KFold."""
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    fold = np.empty(n, dtype=int)
    fold[order] = np.arange(n) % n_folds
    return fold


def indep_timing_hat(P: np.ndarray, *, n_folds: int = 10, seed: int = 0, max_shift: int = 60) -> np.ndarray:
    """Cross-fit matched-filter timing estimate. Template from the training rows of MY fold split;
    correlation over shifts computed as a single matrix product over a stacked shift bank rather
    than a python loop over np.roll."""
    n, T = P.shape
    fold = _my_folds(n, n_folds, seed)
    shifts = np.arange(-max_shift, max_shift + 1)
    out = np.full(n, np.nan)
    for f in range(n_folds):
        te = np.flatnonzero(fold == f)
        tr = np.flatnonzero(fold != f)
        if te.size == 0 or tr.size == 0:
            continue
        template = P[tr].mean(axis=0)
        template = template - template.mean()
        bank = np.stack([np.roll(template, s) for s in shifts])          # (n_shift, T)
        Xc = P[te] - P[te].mean(axis=1, keepdims=True)                   # (n_te, T)
        scores = Xc @ bank.T                                            # (n_te, n_shift)
        out[te] = shifts[np.argmax(scores, axis=1)]
    return out


# ---------------------------------------------------------------------------------------------
# independent held-out predictive gain (OLS, numpy only)
# ---------------------------------------------------------------------------------------------
def _ols_cv_pred(X: np.ndarray, y: np.ndarray, fold: np.ndarray, n_folds: int) -> np.ndarray:
    n = len(y)
    pred = np.full(n, np.nan)
    for f in range(n_folds):
        te = np.flatnonzero(fold == f)
        tr = np.flatnonzero(fold != f)
        A = np.hstack([np.ones((tr.size, 1)), X[tr]])
        coef, *_ = np.linalg.lstsq(A, y[tr], rcond=None)
        Ate = np.hstack([np.ones((te.size, 1)), X[te]])
        pred[te] = Ate @ coef
    return pred


def _r2(y: np.ndarray, p: np.ndarray) -> float:
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def indep_delta(feat: dict, Z_parts: list[np.ndarray], *, n_folds: int = 10, seed: int = 0) -> dict:
    """Delta = R2(M3) - R2(M2), M2 = own_history + Z, M3 = M2 + lag features.
    OLS, 10 folds, no shrinkage, no scaling. Returns per-row held-out predictions too."""
    y = feat["outcome"]
    own = feat["own_history"].reshape(-1, 1)
    lag = feat["lag_features"]
    Z = [z.reshape(-1, 1) for z in Z_parts]
    X_M2 = np.hstack([own] + Z) if Z else own
    X_M3 = np.hstack([X_M2, lag])
    fold = _my_folds(len(y), n_folds, seed + 7717)
    p2 = _ols_cv_pred(X_M2, y, fold, n_folds)
    p3 = _ols_cv_pred(X_M3, y, fold, n_folds)
    return {"r2_M2": _r2(y, p2), "r2_M3": _r2(y, p3), "delta": _r2(y, p3) - _r2(y, p2),
            "y": y, "pred_M2": p2, "pred_M3": p3, "fold": fold, "X_M2": X_M2, "lag": lag}


def bootstrap_delta_ci(y, pred_M2, pred_M3, *, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05):
    """Percentile bootstrap over TRIALS of the held-out Delta. Trials are the inferential unit
    (one row = one trial), and the held-out predictions are fixed given the fit, so resampling
    rows gives the sampling variability of the R2 difference at fixed model."""
    rng = np.random.default_rng(seed + 424242)
    n = len(y)
    idx = rng.integers(0, n, size=(n_boot, n))
    yb = y[idx]
    ybar = yb.mean(axis=1, keepdims=True)
    ss_tot = ((yb - ybar) ** 2).sum(axis=1)
    ss2 = ((yb - pred_M2[idx]) ** 2).sum(axis=1)
    ss3 = ((yb - pred_M3[idx]) ** 2).sum(axis=1)
    good = ss_tot > 0
    d = (1 - ss3[good] / ss_tot[good]) - (1 - ss2[good] / ss_tot[good])
    lo, hi = np.quantile(d, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def permutation_delta_p(res: dict, *, n_perm: int = 200, seed: int = 0) -> float:
    """Within-dataset trial-permutation null: shuffle the ROWS of the lag-feature block (breaking
    its alignment with the outcome while preserving its marginal distribution), refit M3 on the
    SAME folds, and compare. This is the decision rule an analyst WITHOUT oracle knowledge of the
    confound could actually apply on real data. R2(M2) is unaffected by the permutation (lag
    features do not enter M2), so only M3 is refit."""
    rng = np.random.default_rng(seed + 31337)
    y, fold, X_M2, lag = res["y"], res["fold"], res["X_M2"], res["lag"]
    n_folds = int(fold.max()) + 1
    obs = res["delta"]
    r2_M2 = res["r2_M2"]
    null = np.empty(n_perm)
    n = len(y)
    for b in range(n_perm):
        perm = rng.permutation(n)
        X3 = np.hstack([X_M2, lag[perm]])
        null[b] = _r2(y, _ols_cv_pred(X3, y, fold, n_folds)) - r2_M2
    return float((1 + np.sum(null >= obs)) / (n_perm + 1))


def proxy_exact_r_linear(true_gain, r, rng):
    """Behavioural proxy B with EXACT finite-sample Pearson r against true_gain (Gram-Schmidt).
    Defined here rather than in the V2 sweep script so V4 can import it without executing that
    script's module-level sweep."""
    g = np.asarray(true_gain, dtype=float)
    g = g - g.mean()
    u = g / np.linalg.norm(g)
    e = rng.normal(0, 1, len(g))
    e = e - e.mean()
    e = e - (e @ u) * u
    v = e / np.linalg.norm(e)
    return r * u + np.sqrt(max(1 - r ** 2, 0.0)) * v
