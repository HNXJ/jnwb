"""omission.jnwb_ext.spk_lfp_nested -- nested-CV re-estimation of incremental predictive
dependence, with sensitivity and positive controls (2026-08-29, Hamm).

WHY THIS MODULE EXISTS
    The fixed-alpha pilot returned R^2_nuisance ~ 0.20 with delta_pred < 0 everywhere, scaling
    steeply in 1/n. That result cannot distinguish

        "past LFP carries no incremental signal"   from
        "alpha = 1 penalises the enlarged model inadequately".

    This module re-estimates the primary quantity with regularisation tuned INSIDE each training
    fold, retains per-fold quantities, and adds the controls that make a null interpretable.

    The original fixed-alpha path in spk_lfp_pilot.py is left untouched and is re-run here as a
    historical reference arm, so the two are comparable line-for-line.

ESTIMAND -- UNCHANGED
    Incremental predictive dependence of subsequent firing on PAST band-specific LFP state,
    beyond spike history. NOT causal, NOT directional. The causal-identification branch is
    CONFIRMED closed (causal-identification-branch-seal-20260828.json). Required terminology:
    "incremental predictive dependence" / "past-conditioned predictive association".

THE FIVE ARMS
    fixed        past LFP, alpha = 1                  historical reference
    nested       past LFP, alpha tuned in-fold        PRIMARY ESTIMATOR
    concurrent   post-event LFP, alpha tuned          SENSITIVITY control, NOT a positive control
    permuted     past LFP, trial correspondence       NEGATIVE control
                 destroyed, alpha tuned
    injected     past LFP, with a known past-LFP      POSITIVE SENSITIVITY control, beta sweep
                 contribution added to the target

    The concurrent arm is deliberately NOT called a positive control. Post-event LFP shares
    instantaneous common drive with firing and can carry spike contamination (especially at high
    frequencies). delta > 0 there would show the pipeline can extract SOME contemporaneous
    SPK-LFP dependence; it would NOT establish sensitivity to a PAST-LFP effect.

INJECTION GEOMETRY -- AND WHY THE RESULTING POWER IS AN UPPER BOUND
    y_inject = y + beta * sd(y) * u,  u = z(L @ w) with w equal across lag intervals.

    The injected signal is built from the CELL'S OWN REAL LAG-FEATURE MATRIX, so it inherits the
    actual n, feature covariance, and collinearity with spike history. Equal weights across the
    four intervals is the geometry the distributed-lag model detects most easily (a sustained
    past-power effect rather than one localised to a single interval), so the detection rate
    reported from it is an UPPER BOUND on this pipeline's sensitivity, not a typical case.

    Note the injection is added to the OBSERVED target, so the nuisance model is refit on the
    injected target too: delta_inject = R^2_M3(y_inj) - R^2_M2(y_inj). Any part of u already
    predictable from spike history is therefore correctly NOT credited as incremental.

NESTED TUNING
    RidgeCV with alphas swept by efficient leave-one-out generalised CV, fit on the TRAINING
    fold only. The outer held-out trials never participate in choosing alpha. M2 and M3 are
    tuned independently -- the enlarged model is allowed its own penalty, which is the whole
    point of the comparison.

PER-FOLD BASELINE CONVENTION
    Per-fold R^2 uses the TRAINING fold's mean as the null predictor (stable on small test
    folds, unlike the test fold's own mean). Both models in a fold share that baseline, so it
    cancels exactly in delta_k = R^2_M3,k - R^2_M2,k. Pooled out-of-fold R^2 is also reported
    using the global mean, for line-for-line comparability with the fixed-alpha run.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.model_selection import KFold

from omission.jnwb_ext.spk_lfp_pilot import LAG_INTERVALS_MS

# Broad enough that the low-n cells can select genuinely strong shrinkage if that is what the
# data want -- the leading alternative explanation for delta < 0 must be able to express itself.
ALPHAS: np.ndarray = np.logspace(-2.0, 4.0, 13)

BETA_LEVELS: tuple[float, ...] = (0.0, 0.025, 0.05, 0.10, 0.20, 0.40)

MIN_TRIALS = 40


class _FloorScaler:
    """StandardScaler with a variance floor.

    sklearn's StandardScaler only guards EXACTLY-zero variance; a column with train-fold std of
    ~5e-9 divides float noise up into 1e6-1e8 predictions. That defect produced a delta of
    +159,020,991 in the distributed-lag work before it was caught. Same guard, same reason.
    """

    def __init__(self, floor: float = 1e-4):
        self.floor = floor

    def fit(self, X: np.ndarray) -> "_FloorScaler":
        X = np.asarray(X, dtype=float)
        self.mean_ = X.mean(axis=0)
        std = X.std(axis=0)
        self.scale_ = np.where(std < self.floor, 1.0, std)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=float) - self.mean_) / self.scale_


def _fold_r2(y_true: np.ndarray, y_pred: np.ndarray, baseline: float) -> float:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - baseline) ** 2))
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def cv_fit(X: np.ndarray, y: np.ndarray, *, n_splits: int = 5, seed: int = 0,
           alpha: float | None = None, alphas: np.ndarray = ALPHAS) -> dict:
    """Trial-blocked held-out fit. ``alpha=None`` tunes per training fold via RidgeCV.

    Rows are physical trials (canonical identity (session, absolute onset)), so KFold over rows
    is trial-blocked by construction. Scaler, alpha selection and model are all fit on the
    training fold only.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    nan = {"fold_r2": [], "fold_alpha": [], "pooled_r2": float("nan"), "n": int(n)}
    if n < n_splits * 2 or np.std(y) == 0:
        return nan

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    pred = np.full(n, np.nan)
    fold_r2: list[float] = []
    fold_alpha: list[float] = []

    for tr, te in kf.split(X):
        sc = _FloorScaler().fit(X[tr])
        Xtr, Xte = sc.transform(X[tr]), sc.transform(X[te])
        if alpha is None:
            model = RidgeCV(alphas=alphas).fit(Xtr, y[tr])   # LOO-GCV on TRAIN only
            chosen = float(model.alpha_)
        else:
            model = Ridge(alpha=alpha).fit(Xtr, y[tr])
            chosen = float(alpha)
        p = model.predict(Xte)
        pred[te] = p
        fold_r2.append(_fold_r2(y[te], p, float(y[tr].mean())))
        fold_alpha.append(chosen)

    return {"fold_r2": fold_r2, "fold_alpha": fold_alpha,
            "pooled_r2": _fold_r2(y, pred, float(y.mean())), "n": int(n)}


def _clean(lag_features: np.ndarray, spike_history: np.ndarray, y: np.ndarray,
           nuisance: np.ndarray | None):
    Z = spike_history.reshape(-1, 1)
    if nuisance is not None and nuisance.size:
        Z = np.column_stack([Z, nuisance])
    L = np.asarray(lag_features, dtype=float)
    ok = (np.isfinite(y) & np.all(np.isfinite(Z), axis=1) & np.all(np.isfinite(L), axis=1))
    return Z[ok], L[ok], np.asarray(y, dtype=float)[ok], int(ok.sum())


def delta_arm(lag_features: np.ndarray, spike_history: np.ndarray, y: np.ndarray, *,
              nuisance: np.ndarray | None = None, alpha: float | None = None,
              n_splits: int = 5, seed: int = 0) -> dict:
    """One arm: delta = R^2(nuisance + LFP features) - R^2(nuisance), with per-fold retention."""
    Z, L, yc, n_ok = _clean(lag_features, spike_history, y, nuisance)
    if n_ok < MIN_TRIALS:
        return {"delta_pooled": float("nan"), "delta_fold_mean": float("nan"),
                "delta_fold_median": float("nan"), "delta_fold_sd": float("nan"),
                "delta_fold_min": float("nan"), "delta_fold_max": float("nan"),
                "frac_folds_positive": float("nan"),
                "r2_m2_pooled": float("nan"), "r2_m3_pooled": float("nan"),
                "alpha_m2_median": float("nan"), "alpha_m3_median": float("nan"),
                "n_trials_used": n_ok}

    m2 = cv_fit(Z, yc, n_splits=n_splits, seed=seed, alpha=alpha)
    m3 = cv_fit(np.column_stack([Z, L]), yc, n_splits=n_splits, seed=seed, alpha=alpha)
    dk = np.asarray(m3["fold_r2"], dtype=float) - np.asarray(m2["fold_r2"], dtype=float)

    return {
        "delta_pooled": float(m3["pooled_r2"] - m2["pooled_r2"]),
        "delta_fold_mean": float(np.nanmean(dk)) if dk.size else float("nan"),
        "delta_fold_median": float(np.nanmedian(dk)) if dk.size else float("nan"),
        "delta_fold_sd": float(np.nanstd(dk, ddof=1)) if dk.size > 1 else float("nan"),
        "delta_fold_min": float(np.nanmin(dk)) if dk.size else float("nan"),
        "delta_fold_max": float(np.nanmax(dk)) if dk.size else float("nan"),
        "frac_folds_positive": float(np.mean(dk > 0)) if dk.size else float("nan"),
        "r2_m2_pooled": float(m2["pooled_r2"]), "r2_m3_pooled": float(m3["pooled_r2"]),
        "alpha_m2_median": float(np.median(m2["fold_alpha"])) if m2["fold_alpha"] else float("nan"),
        "alpha_m3_median": float(np.median(m3["fold_alpha"])) if m3["fold_alpha"] else float("nan"),
        "n_trials_used": n_ok,
    }


def inject_past_lfp_signal(y: np.ndarray, lag_features: np.ndarray, beta: float) -> np.ndarray:
    """y + beta * sd(y) * z(L @ w), equal weights w across lag intervals.

    Built from the cell's OWN real lag features, so the injected effect inherits the actual
    trial count, feature covariance and collinearity with spike history. Equal weights is the
    most detectable geometry -- see module docstring on why the resulting power is an upper bound.
    """
    L = np.asarray(lag_features, dtype=float)
    y = np.asarray(y, dtype=float)
    if beta == 0.0:
        return y.copy()
    Lz = (L - np.nanmean(L, axis=0)) / np.where(np.nanstd(L, axis=0) < 1e-12, 1.0,
                                                np.nanstd(L, axis=0))
    u = Lz.mean(axis=1)
    su = np.nanstd(u)
    if not np.isfinite(su) or su < 1e-12:
        return y.copy()
    return y + beta * np.nanstd(y) * (u - np.nanmean(u)) / su


def permute_lag_features(lag_features: np.ndarray, *, seed: int) -> np.ndarray:
    """Destroy trial correspondence while preserving the feature covariance structure.

    Rows are permuted as whole rows, so the four lag intervals keep their mutual correlations
    and only their pairing with the target is broken -- the correct null for "does THIS trial's
    past LFP predict THIS trial's firing".
    """
    rng = np.random.default_rng(seed)
    L = np.asarray(lag_features, dtype=float)
    return L[rng.permutation(len(L))]


def lead_interval_features(env: np.ndarray, time_ms: np.ndarray, event_ms: float,
                           intervals=LAG_INTERVALS_MS) -> np.ndarray:
    """Mean band power in each interval AFTER the event: (a, b) -> [event + a, event + b).

    Deliberately overlaps the response window. This is the contemporaneous/sensitivity arm and
    is NOT causally admissible as evidence about past dependence.
    """
    out = np.empty((env.shape[0], len(intervals)))
    for k, (a, b) in enumerate(intervals):
        mask = (time_ms >= event_ms + a) & (time_ms < event_ms + b)
        out[:, k] = env[:, mask].mean(axis=1) if mask.any() else np.nan
    return out


def all_arms(lag_features: np.ndarray, lead_features: np.ndarray, spike_history: np.ndarray,
             y: np.ndarray, *, nuisance: np.ndarray | None = None, n_splits: int = 5,
             seed: int = 0, betas: tuple[float, ...] = BETA_LEVELS) -> dict:
    """Run the full re-run matrix for one cell. Returns {arm_name: delta_arm(...)}."""
    out: dict[str, dict] = {}
    out["fixed"] = delta_arm(lag_features, spike_history, y, nuisance=nuisance,
                             alpha=1.0, n_splits=n_splits, seed=seed)
    out["nested"] = delta_arm(lag_features, spike_history, y, nuisance=nuisance,
                              alpha=None, n_splits=n_splits, seed=seed)
    out["concurrent"] = delta_arm(lead_features, spike_history, y, nuisance=nuisance,
                                  alpha=None, n_splits=n_splits, seed=seed)
    out["permuted"] = delta_arm(permute_lag_features(lag_features, seed=seed + 9973),
                                spike_history, y, nuisance=nuisance, alpha=None,
                                n_splits=n_splits, seed=seed)
    for b in betas:
        out[f"inject_{b:g}"] = delta_arm(
            lag_features, spike_history, inject_past_lfp_signal(y, lag_features, b),
            nuisance=nuisance, alpha=None, n_splits=n_splits, seed=seed)
    return out
