"""omission.jnwb_ext.distributed_lag_model -- causal-time, past-conditioned predictive coupling.

2026-08-28 (Hamm). Pivot of the primary P4 development effort away from single-peak lag
correlation (argmax_tau C(tau)) toward a nested, held-out-validated predictive model. Motivation,
converging from four independent findings this session: (1) common causes (shared timing jitter,
shared amplitude/gain state) generate spurious lag-correlation peaks that ordinary and even
nuisance-matched permutation nulls struggle to fully control; (2) single-peak argmax lag
estimation is itself unstable under realistic superposed dynamics (theta's ~8% catastrophic
outliers, B2's ~6ms interference bias from a second confound-correlated response component, a
reproducible sign flip at long lags). The primary question this module answers is:

    Does past LFP state improve prediction of future firing beyond the neuron's own history and
    measured common causes -- and over what temporal range does that incremental information
    occur?

NOT: where is the largest cross-correlation peak?

SCOPE NOTE: this is a TRIAL-LEVEL summary-regression instantiation of Hamm's point-process
formulation (g(lambda_u(t)) = alpha + H_S(t) + Z(t) + sum_b sum_tau beta_{b,tau} P_b(t-tau)), not
a full time-resolved GLM fit at every sample. Each physical trial is collapsed to one row: an
outcome summary in a designated RESPONSE WINDOW, an own-history summary from just before it, safe
common-cause covariates, and distributed-lag LFP features from progressively earlier windows.
This is tractable to implement and validate rigorously within this cycle's scope and is faithful
to the model's core logic (nested models, held-out predictive gain, distributed lag
representation, safe-covariate conditioning) -- promotion to a genuine time-resolved point-process
fit is future work, not done here.

Nested models (Hamm's M0-M3 + the M3_bad regression test):
    M0        : own-history feature only
    M1        : M0 + event/time covariates (trial-constant; degenerate to M0 in a single-condition
                synthetic benchmark with no real condition/position variation -- documented, not
                hidden)
    M2        : M1 + safe common-cause covariates Z (pre-event amplitude/gain proxy, matched-filter
                timing proxy -- both estimated from P alone, never from R, per the same safety
                argument used for Candidates B2/C's covariates)
    M3        : M2 + distributed-lag LFP features (several causal windows of P at increasing
                pre-response lag)
    M3_bad    : M1 + distributed-lag LFP features, WITHOUT Z -- the crucial negative control.
                The synthetic common-driver generator should make M3_bad appear to gain
                predictive power from LFP (confound leaking through unconditioned lag features)
                while properly-conditioned M3 removes that spurious gain. This is a direct
                regression test that the Z-conditioning machinery does meaningful work, not
                cosmetic.

Primary statistic: incremental HELD-OUT predictive gain, Delta_LFP = Perf(M3) - Perf(M2), using
identical CV folds for every nested model (grouped at the trial level -- since each row already
IS one physical trial in this scoping, K-fold CV over rows is equivalent to grouping by trial;
this is stated explicitly rather than left implicit).
"""
from __future__ import annotations

import hashlib

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.preprocessing import PolynomialFeatures, SplineTransformer


class _FloorScaler:
    """StandardScaler with a variance FLOOR (2026-08-28, found during reverse-direction
    benchmarking): sklearn's own StandardScaler only guards against EXACTLY-zero variance,
    clamping scale_ to 1 there. An analytic oracle template column can have a train-fold std that
    is nonzero but numerically negligible (e.g. ~5e-9, when the true expected value is genuinely
    near-zero because a narrow-kernel signal's analytic support doesn't reach a given window --
    this happens for real in the reverse-direction dataset, where a channel's shared-kernel
    identity is swapped into a fixed absolute-time window it doesn't naturally reach). Dividing
    by that tiny-but-nonzero scale amplifies ordinary train/test floating-point-level differences
    into predictions of order 1e6-1e8, producing an R^2 that is a numerical artifact, not a
    result -- reproduced directly: sklearn's StandardScaler on a std~1e-21 column DOES clamp
    correctly (scale_=1), but a std~5e-9 column does not, and that was enough to blow up held-out
    R^2 by orders of magnitude in the reverse-direction battery. floor=1e-4 is well above any
    such artifact-scale std while remaining far below any genuinely informative feature's scale
    in this module's z-scored/kernel-amplitude-bounded (~0-1) feature space."""

    def __init__(self, floor: float = 1e-4):
        self.floor = floor

    def fit(self, X: np.ndarray) -> "_FloorScaler":
        self.mean_ = X.mean(axis=0)
        std = X.std(axis=0)
        self.scale_ = np.where(std < self.floor, 1.0, std)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_) / self.scale_


StandardScaler = _FloorScaler

from omission.jnwb_ext.common_driver_control import (
    _gaussian_kernel, _matched_filter_lag, estimate_amplitude_covariate,
)


def build_trial_level_dataset(
    P_trials: np.ndarray, R_trials: np.ndarray, *,
    baseline_window=(0, 80), history_window=(180, 205), response_window=(210, 230),
    lag_bins_ms=((130, 150), (150, 170), (170, 190), (190, 210)),
    timing_n_folds: int = 5, seed: int = 0,
):
    """Collapse each trial to one row of features + one outcome. All P-derived covariates
    (timing, amplitude, lag-bin features) come from P alone; R contributes only its own-history
    feature (from history_window, strictly before response_window) and the outcome itself (from
    response_window) -- R is never used to build a covariate that conditions on itself.

    Returns a dict of arrays, each shape (n_trials,) or (n_trials, n_lag_bins) for lag_features,
    plus the ground-truth-free feature blocks needed to assemble M0-M3/M3_bad design matrices.
    """
    n_trials = P_trials.shape[0]
    lo_b, hi_b = baseline_window
    lo_h, hi_h = history_window
    lo_r, hi_r = response_window

    outcome = R_trials[:, lo_r:hi_r].mean(axis=1)
    own_history = R_trials[:, lo_h:hi_h].mean(axis=1)

    amplitude = estimate_amplitude_covariate(P_trials, baseline_window)

    rng = np.random.default_rng(seed)
    fold = rng.integers(0, timing_n_folds, size=n_trials)
    timing = np.empty(n_trials)
    for f in range(timing_n_folds):
        test_idx = np.flatnonzero(fold == f)
        train_idx = np.flatnonzero(fold != f)
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        template = P_trials[train_idx].mean(axis=0)
        for i in test_idx:
            timing[i] = _matched_filter_lag(P_trials[i], template, max_shift=60)

    lag_features = np.stack([P_trials[:, lo:hi].mean(axis=1) for lo, hi in lag_bins_ms], axis=1)

    return {
        "outcome": outcome, "own_history": own_history, "amplitude": amplitude,
        "timing": timing, "lag_features": lag_features, "lag_bins_ms": lag_bins_ms,
    }


def _held_out_predict(X: np.ndarray, y: np.ndarray, *, n_splits: int = 5, alpha: float = 1.0, seed: int = 0):
    """Ridge regression, held-out predictions returned IN ORIGINAL ROW ORDER (not concatenated
    fold order) so per-trial residuals can be matched back to per-trial ground truth. Same
    scaler-inside-fold discipline as _held_out_r2."""
    n = len(y)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_pred = np.full(n, np.nan)
    for train_idx, test_idx in kf.split(X):
        scaler = StandardScaler().fit(X[train_idx])
        Xtr, Xte = scaler.transform(X[train_idx]), scaler.transform(X[test_idx])
        model = Ridge(alpha=alpha).fit(Xtr, y[train_idx])
        y_pred[test_idx] = model.predict(Xte)
    return y_pred


def _r2_from_pred(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan


def _held_out_r2(X: np.ndarray, y: np.ndarray, *, n_splits: int = 5, alpha: float = 1.0, seed: int = 0):
    """Ridge regression, held-out R^2 via KFold (== grouped-by-trial CV, see module docstring),
    scaler/regularization fit INSIDE each training fold only (no leakage)."""
    y_pred = _held_out_predict(X, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return _r2_from_pred(y, y_pred)


def fit_nested_models(dataset: dict, *, n_splits: int = 5, alpha: float = 1.0, seed: int = 0,
                       include_event_covariate: bool = False) -> dict:
    """Fits M0/M1/M2/M3/M3_bad on the SAME held-out folds (same KFold seed -> same splits, since
    KFold(shuffle=True, random_state=seed) is deterministic given seed) and reports held-out R^2
    for each, plus Delta_LFP = R2(M3)-R2(M2) and Delta_LFP_bad = R2(M3_bad)-R2(M1).

    include_event_covariate: in this single-condition synthetic benchmark there is no genuine
    condition/position variation across trials, so M1's only possible addition over M0 is a
    constant (uninformative) trial-index-like covariate -- included only if explicitly requested,
    documented as expected to contribute ~0 by design in this synthetic setting, not real-data.
    """
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    amp = dataset["amplitude"].reshape(-1, 1)
    timing = dataset["timing"].reshape(-1, 1)
    lag = dataset["lag_features"]
    n = len(y)

    X_M0 = own_hist
    if include_event_covariate:
        event_cov = np.arange(n).reshape(-1, 1).astype(float)  # placeholder trial-index nuisance
        X_M1 = np.hstack([own_hist, event_cov])
    else:
        X_M1 = own_hist
    X_M2 = np.hstack([X_M1, amp, timing])
    X_M3 = np.hstack([X_M2, lag])
    X_M3_bad = np.hstack([X_M1, lag])

    r2 = {name: _held_out_r2(X, y, n_splits=n_splits, alpha=alpha, seed=seed)
          for name, X in [("M0", X_M0), ("M1", X_M1), ("M2", X_M2), ("M3", X_M3), ("M3_bad", X_M3_bad)]}

    return {
        "r2": r2,
        "delta_lfp": r2["M3"] - r2["M2"],
        "delta_lfp_bad": r2["M3_bad"] - r2["M1"],
    }


def held_out_residuals_M2(dataset: dict, *, n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> np.ndarray:
    """Held-out residuals e_M2 = y - yhat_M2, in original trial order, for diagnosing what
    confound information M2's conditioning failed to remove (2026-08-28 diagnostic, item 1)."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    amp = dataset["amplitude"].reshape(-1, 1)
    timing = dataset["timing"].reshape(-1, 1)
    X_M2 = np.hstack([own_hist, amp, timing])
    y_pred = _held_out_predict(X_M2, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return y - y_pred


def predict_latent_from_features(X: np.ndarray, target: np.ndarray, *, n_splits: int = 5,
                                  alpha: float = 1.0, seed: int = 0) -> dict:
    """Held-out R^2 and Pearson r predicting `target` (e.g. true_jitter/true_gain, or an M2
    residual) from feature block X (item 1/2 diagnostic: how much latent-nuisance information a
    given feature block retains)."""
    X = np.asarray(X)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    y_pred = _held_out_predict(X, target, n_splits=n_splits, alpha=alpha, seed=seed)
    r2 = _r2_from_pred(target, y_pred)
    pear = float(np.corrcoef(target, y_pred)[0, 1]) if np.std(y_pred) > 0 and np.std(target) > 0 else float("nan")
    return {"held_out_r2": r2, "pearson_pred_vs_true": pear}


def fit_oracle_nested_models(dataset: dict, true_jitter: np.ndarray, true_gain: np.ndarray, *,
                              n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> dict:
    """Item 3 diagnostic: replace the noisy proxy Z with the GROUND-TRUTH nuisance state
    (available only because this is synthetic data). M2_oracle = M1 + true_jitter + true_gain;
    M3_oracle = M2_oracle + lag features. Decisive test of architecture vs. proxy-fidelity as the
    failure mechanism -- see module/caller docstrings."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    lag = dataset["lag_features"]
    oracle_z = np.stack([true_jitter, true_gain], axis=1)

    X_M1 = own_hist
    X_M2_oracle = np.hstack([X_M1, oracle_z])
    X_M3_oracle = np.hstack([X_M2_oracle, lag])

    r2_M1 = _held_out_r2(X_M1, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M2o = _held_out_r2(X_M2_oracle, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M3o = _held_out_r2(X_M3_oracle, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return {"r2_M1": r2_M1, "r2_M2_oracle": r2_M2o, "r2_M3_oracle": r2_M3o,
            "delta_oracle": r2_M3o - r2_M2o}


def held_out_residuals_M2_oracle(dataset: dict, true_jitter: np.ndarray, true_gain: np.ndarray, *,
                                  n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> np.ndarray:
    """Held-out residuals from the LINEAR oracle M2 (M1 + true_jitter + true_gain), in original
    trial order -- used to test whether what's left over is recoverable NONLINEARLY from the same
    ground-truth latents (2026-08-28 follow-up diagnostic: is the oracle-conditioning failure on
    the timing confound a nonlinearity problem, not a proxy-fidelity problem?)."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    oracle_z = np.stack([true_jitter, true_gain], axis=1)
    X_M2_oracle = np.hstack([own_hist, oracle_z])
    y_pred = _held_out_predict(X_M2_oracle, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return y - y_pred


def nonlinear_predict_r2(X: np.ndarray, target: np.ndarray, *, n_splits: int = 5, seed: int = 0) -> float:
    """Held-out R^2 predicting `target` from X using a RandomForestRegressor (captures
    nonlinear/non-monotonic structure a linear Ridge model cannot), same KFold discipline as
    the linear diagnostics for direct comparability."""
    from sklearn.ensemble import RandomForestRegressor
    X = np.asarray(X)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    n = len(target)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_pred = np.full(n, np.nan)
    for train_idx, test_idx in kf.split(X):
        model = RandomForestRegressor(n_estimators=300, max_depth=4, random_state=seed).fit(X[train_idx], target[train_idx])
        y_pred[test_idx] = model.predict(X[test_idx])
    return _r2_from_pred(target, y_pred)


def fit_noisy_oracle_nested_models(dataset: dict, true_jitter: np.ndarray, true_gain: np.ndarray, *,
                                    proxy_noise_sd_jitter: float = 0.0, proxy_noise_sd_gain: float = 0.0,
                                    n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> dict:
    """Item 4 diagnostic: interpolate between oracle Z (noise=0) and a degraded proxy by adding
    Gaussian measurement error of specified SD to the ground-truth nuisance state before
    conditioning. Sweeping proxy_noise_sd_* from 0 upward traces the errors-in-variables curve
    the oracle-vs-current-Z comparison is expected to sit on if proxy fidelity is the mechanism."""
    rng = np.random.default_rng(seed + 900000)
    noisy_jitter = true_jitter + rng.normal(0, proxy_noise_sd_jitter, size=len(true_jitter)) if proxy_noise_sd_jitter > 0 else true_jitter.copy()
    noisy_gain = true_gain + rng.normal(0, proxy_noise_sd_gain, size=len(true_gain)) if proxy_noise_sd_gain > 0 else true_gain.copy()
    return fit_oracle_nested_models(dataset, noisy_jitter, noisy_gain, n_splits=n_splits, alpha=alpha, seed=seed)


def _poly_expand(x: np.ndarray, degree: int) -> np.ndarray:
    """Deterministic (data-independent) polynomial expansion -- safe to compute globally rather
    than inside each CV fold, since PolynomialFeatures has no fitted parameters for a fixed
    degree (unlike SplineTransformer's data-dependent knot placement)."""
    return PolynomialFeatures(degree=degree, include_bias=False).fit_transform(x.reshape(-1, 1))


def _held_out_r2_spline(x: np.ndarray, y: np.ndarray, *, n_knots: int = 4, degree: int = 3,
                         n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> float:
    """Held-out R^2 of y ~ spline(x), with the spline's knot placement (quantile-based, hence
    data-dependent) fit ONLY inside each training fold -- unlike polynomial powers, spline knots
    genuinely leak test-set information if fit on the full dataset."""
    x = x.reshape(-1, 1)
    n = len(y)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_pred = np.full(n, np.nan)
    for train_idx, test_idx in kf.split(x):
        spline = SplineTransformer(n_knots=n_knots, degree=degree).fit(x[train_idx])
        Ztr, Zte = spline.transform(x[train_idx]), spline.transform(x[test_idx])
        scaler = StandardScaler().fit(Ztr)
        model = Ridge(alpha=alpha).fit(scaler.transform(Ztr), y[train_idx])
        y_pred[test_idx] = model.predict(scaler.transform(Zte))
    return _r2_from_pred(y, y_pred)


def feature_vs_jitter_nonlinearity(feature: np.ndarray, true_jitter: np.ndarray, *,
                                    n_splits: int = 5, seed: int = 0) -> dict:
    """Item 2 diagnostic: held-out R^2 of ONE feature (outcome, own_history, or a single lag bin)
    predicted from true_jitter alone, at increasing representational capacity (linear / quadratic
    / cubic / spline). A feature whose dependence on jitter is genuinely nonlinear should show
    R^2 rising sharply from linear to quadratic/spline; a feature that's already linear in jitter
    should show little further gain."""
    r2_linear = _held_out_r2(true_jitter.reshape(-1, 1), feature, n_splits=n_splits, seed=seed)
    r2_quad = _held_out_r2(_poly_expand(true_jitter, 2), feature, n_splits=n_splits, seed=seed)
    r2_cubic = _held_out_r2(_poly_expand(true_jitter, 3), feature, n_splits=n_splits, seed=seed)
    r2_spline = _held_out_r2_spline(true_jitter, feature, n_splits=n_splits, seed=seed)
    return {"linear": r2_linear, "quadratic": r2_quad, "cubic": r2_cubic, "spline": r2_spline}


def fit_structured_timing_oracle(dataset: dict, timing_Z: np.ndarray, *, gain_Z: np.ndarray | None = None,
                                  n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> dict:
    """Item 3: M2 = M1(own_history) + timing_Z (any representation: linear/poly/spline
    expansion of true_jitter) [+ gain_Z if given, for combined-scenario reuse]; M3 = M2 + lag
    features. All fitting (scaling, Ridge) happens inside training folds via _held_out_r2; the
    caller is responsible for ensuring timing_Z/gain_Z themselves were built without test-fold
    leakage (deterministic poly transforms are safe globally; spline needs _held_out_r2_spline
    instead of this function -- see fit_structured_timing_oracle_spline)."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    lag = dataset["lag_features"]
    X_M1 = own_hist
    Z_parts = [timing_Z] if gain_Z is None else [timing_Z, gain_Z.reshape(-1, 1) if gain_Z.ndim == 1 else gain_Z]
    X_M2 = np.hstack([X_M1] + Z_parts)
    X_M3 = np.hstack([X_M2, lag])
    r2_M1 = _held_out_r2(X_M1, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M2 = _held_out_r2(X_M2, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M3 = _held_out_r2(X_M3, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return {"r2_M1": r2_M1, "r2_M2": r2_M2, "r2_M3": r2_M3, "delta": r2_M3 - r2_M2}


def fit_structured_timing_oracle_spline(dataset: dict, true_jitter: np.ndarray, *,
                                         gain_Z: np.ndarray | None = None, n_knots: int = 4,
                                         degree: int = 3, n_splits: int = 5, alpha: float = 1.0,
                                         seed: int = 0) -> dict:
    """Same as fit_structured_timing_oracle but with a spline representation of true_jitter whose
    knots are fit strictly inside each training fold (data-dependent transform -- see
    _held_out_r2_spline's docstring)."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    lag = dataset["lag_features"]
    x = true_jitter.reshape(-1, 1)
    n = len(y)
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_pred_M1 = np.full(n, np.nan)
    y_pred_M2 = np.full(n, np.nan)
    y_pred_M3 = np.full(n, np.nan)
    for train_idx, test_idx in kf.split(x):
        spline = SplineTransformer(n_knots=n_knots, degree=degree).fit(x[train_idx])
        Ztr, Zte = spline.transform(x[train_idx]), spline.transform(x[test_idx])
        gtr = [gain_Z[train_idx].reshape(-1, 1)] if gain_Z is not None else []
        gte = [gain_Z[test_idx].reshape(-1, 1)] if gain_Z is not None else []

        X_M1_tr, X_M1_te = own_hist[train_idx], own_hist[test_idx]
        X_M2_tr = np.hstack([X_M1_tr, Ztr] + gtr)
        X_M2_te = np.hstack([X_M1_te, Zte] + gte)
        X_M3_tr = np.hstack([X_M2_tr, lag[train_idx]])
        X_M3_te = np.hstack([X_M2_te, lag[test_idx]])

        for Xtr, Xte, store in [(X_M1_tr, X_M1_te, y_pred_M1), (X_M2_tr, X_M2_te, y_pred_M2),
                                 (X_M3_tr, X_M3_te, y_pred_M3)]:
            scaler = StandardScaler().fit(Xtr)
            model = Ridge(alpha=alpha).fit(scaler.transform(Xtr), y[train_idx])
            store[test_idx] = model.predict(scaler.transform(Xte))

    r2_M1 = _r2_from_pred(y, y_pred_M1)
    r2_M2 = _r2_from_pred(y, y_pred_M2)
    r2_M3 = _r2_from_pred(y, y_pred_M3)
    return {"r2_M1": r2_M1, "r2_M2": r2_M2, "r2_M3": r2_M3, "delta": r2_M3 - r2_M2}


def translated_template_nuisance(true_jitter: np.ndarray, true_gain: np.ndarray, *, trial_len: int = 400,
                                  p_center: float = 150.0, p_sigma: float = 25.0,
                                  r_center: float = 220.0, r_sigma: float = 5.0,
                                  history_window=(180, 205), lag_bins_ms=((130, 150), (150, 170), (170, 190), (190, 210))):
    """Item 4: the EXACT analytic expected value of each M3-relevant feature under the confound
    (jitter+gain) alone, zero coupling -- computed directly from the known generator kernel
    formula (_gaussian_kernel), not estimated from any trial's data. This is the strongest
    possible oracle: it hands the model the precise null-hypothesis shape of every lag-bin
    feature, not just the scalar jitter/gain values, so if confounding still leaks through, the
    problem cannot be nuisance-representation capacity at all.

    Returns (hist_template, lag_template) matching own_history and lag_features shapes.
    """
    t = np.arange(trial_len)
    n = len(true_jitter)
    n_lag = len(lag_bins_ms)
    lo_h, hi_h = history_window
    hist_template = np.empty(n)
    lag_template = np.empty((n, n_lag))
    for i in range(n):
        e_i, gain_i = true_jitter[i], true_gain[i]
        hist_template[i] = gain_i * _gaussian_kernel(t[lo_h:hi_h], r_center + e_i, r_sigma).mean()
        for k, (lo, hi) in enumerate(lag_bins_ms):
            lag_template[i, k] = gain_i * _gaussian_kernel(t[lo:hi], p_center + e_i, p_sigma).mean()
    return hist_template, lag_template


def fit_translated_template_oracle(dataset: dict, hist_template: np.ndarray, lag_template: np.ndarray, *,
                                    n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> dict:
    """M2_template = own_history(real) + hist_template(analytic) + lag_template(analytic);
    M3_template = M2_template + lag_features(REAL, observed). Tests whether, given the exact
    null-hypothesis shape of the lag features, real observed lag features still show spurious
    incremental gain on zero-coupling data."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    lag = dataset["lag_features"]
    X_M1 = own_hist
    X_M2 = np.hstack([own_hist, hist_template.reshape(-1, 1), lag_template])
    X_M3 = np.hstack([X_M2, lag])
    r2_M1 = _held_out_r2(X_M1, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M2 = _held_out_r2(X_M2, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M3 = _held_out_r2(X_M3, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return {"r2_M1": r2_M1, "r2_M2": r2_M2, "r2_M3": r2_M3, "delta": r2_M3 - r2_M2}


def folds_fingerprint(n_samples: int, n_splits: int, seed: int) -> str:
    """Stable fingerprint of a KFold(n_splits, shuffle=True, random_state=seed) partition over
    n_samples rows. Used to DETECT (not merely document) a caller passing mismatched seeds to
    estimate_timing_nested and fit_nuisance_tier -- see _TimingEstimate."""
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    parts = [",".join(map(str, test_idx)) for _, test_idx in kf.split(np.zeros((n_samples, 1)))]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


class _TimingEstimate(np.ndarray):
    """A plain float ndarray that additionally remembers WHICH cross-validation partition
    produced it (2026-08-29, P2 fix). Subclassing ndarray keeps every existing caller working
    unchanged -- it is an ndarray for all arithmetic, indexing and I/O purposes -- while letting
    fit_nuisance_tier verify that the folds it is about to evaluate on are the same ones the
    timing estimate was cross-fit against. Without this, a caller passing seed=0 to one function
    and seed=1 to the other silently breaks the cross-fitting guarantee with no error and no
    visible symptom (the CONCERN raised by independent verification 2026-08-28: correct at all
    5 call sites, unenforced by the API)."""

    def __new__(cls, values: np.ndarray, fingerprint: str | None = None):
        obj = np.asarray(values, dtype=float).view(cls)
        obj.folds_fingerprint = fingerprint
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        # Slices/views inherit the fingerprint; it is descriptive metadata, not a shape claim.
        self.folds_fingerprint = getattr(obj, "folds_fingerprint", None)


def estimate_timing_nested(P_trials: np.ndarray, *, n_splits: int = 5, seed: int = 0,
                            max_shift: int = 60) -> _TimingEstimate:
    """Matched-filter timing estimate (2026-08-28, observable-Zhat bridge), using the EXACT SAME
    KFold(n_splits, shuffle=True, random_state=seed) fold assignment that the M2/M3 held-out
    evaluation will use (see fit_nuisance_tier below) -- NOT a separately-seeded inner split, as
    the earlier oracle-era `timing` feature in build_trial_level_dataset used. This is what makes
    the estimate strictly cross-fit for the Zhat benchmark's outer evaluation: a test-fold
    trial's timing estimate is built from a template fit on that SAME fold's training trials
    only, so no test trial's own P data (nor any other test-fold trial's) enters its own
    template, and no full-dataset event template ever enters held-out evaluation (Hamm item 7).

    Returns a _TimingEstimate (an ndarray subclass) tagged with the fold partition used, so
    fit_nuisance_tier can REJECT a mismatched-seed pairing instead of silently producing a
    non-cross-fit result (2026-08-29, P2)."""
    n_trials = P_trials.shape[0]
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    shifts = np.full(n_trials, np.nan)
    for train_idx, test_idx in kf.split(P_trials):
        template = P_trials[train_idx].mean(axis=0)
        for i in test_idx:
            shifts[i] = _matched_filter_lag(P_trials[i], template, max_shift)
    return _TimingEstimate(shifts, folds_fingerprint(n_trials, n_splits, seed))


ZHAT_TIER_DEFINITIONS = {
    "Zhat-0_design_only": [],
    "Zhat-1_plus_pre_neural_state": ["amplitude"],
    "Zhat-2_plus_timing_gain": ["amplitude", "timing_hat"],
}


def simulate_behavioral_proxy(true_gain: np.ndarray, *, target_r: float, seed: int = 0) -> np.ndarray:
    """2026-08-28 (Hamm, Zhat-3 synthetic bridge): B_i = true_gain_i + noise, a noisy OBSERVATION
    of the latent gain/state confound (gain -> B, alongside the existing gain -> {P,R}), used to
    test whether a behavioral proxy (real analogue: pupil/gaze pre-event state) can materially
    repair the gain-confound FPR failure found with the current P-baseline amplitude proxy
    (r=+0.28 with true_gain, FPR=1.00). target_r sets the desired Pearson correlation between B
    and true_gain by solving noise_sd from sigma_gain/sigma_noise algebra (r =
    sigma_gain/sqrt(sigma_gain^2+sigma_noise^2)); target_r=0 returns pure noise (no signal),
    target_r->1 approaches a near-oracle behavioral proxy. This is deliberately swept across a
    RANGE (not tuned to a single value) so a real pupil/gaze proxy's empirically-estimated
    reliability can be located on the resulting fidelity->calibration surface, per Hamm's
    explicit instruction not to tune synthetic fidelity to make the real analysis look viable."""
    rng = np.random.default_rng(seed + 950000)
    sigma_gain = float(np.std(true_gain))
    if target_r <= 0:
        return rng.normal(0, 1, size=len(true_gain))
    if target_r >= 1:
        return true_gain.copy()
    sigma_noise = sigma_gain * np.sqrt(1.0 / target_r ** 2 - 1.0)
    return true_gain + rng.normal(0, sigma_noise, size=len(true_gain))


def fit_nuisance_tier(dataset: dict, tier: str, *, timing_hat: np.ndarray | None = None,
                       true_jitter: np.ndarray | None = None, true_gain: np.ndarray | None = None,
                       extra_Z: list[np.ndarray] | None = None,
                       n_splits: int = 5, alpha: float = 1.0, seed: int = 0) -> dict:
    """Fit M1/M2/M3 for one nuisance tier and report held-out Delta_LFP = R2(M3)-R2(M2), for the
    oracle-Z -> observable-Zhat bridge benchmark (2026-08-28).

    tier: one of ZHAT_TIER_DEFINITIONS' keys (Zhat-0/1/2, all OBSERVABLE -- built only from P's
    own pre-response/baseline structure and R's own pre-response history, never from
    true_jitter/true_gain/private-innovation labels) or "oracle" (M2 = own_history + true_jitter
    + true_gain, requires true_jitter/true_gain to be passed -- for comparison only, never a
    real-data-usable tier).

    CAUSAL CLASSIFICATION (Hamm item 3): own_history = PREEXISTING (R's own pre-response-window
    value, strictly prior to the tested outcome); amplitude = COMMON-CAUSE PROXY (P's pre-event
    baseline window, structurally prior to any coupling term by generator construction -- see
    estimate_amplitude_covariate's docstring); timing_hat = COMMON-CAUSE PROXY (matched-filter
    estimate from P alone, cross-fit, never touches R). None of Zhat-0/1/2 condition on a
    POSSIBLE MEDIATOR or OUTCOME -- in particular, timing_hat and amplitude are both built from
    the SAME pre-response P material already isolated as safe by prior validation rounds this
    session, not from post-event P history (which would risk M2 absorbing the exposure M3 is
    meant to test) or post-event R amplitude (explicitly flagged as unsafe by Hamm)."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    lag = dataset["lag_features"]

    if tier == "oracle":
        assert true_jitter is not None and true_gain is not None
        Z_parts = [true_jitter.reshape(-1, 1), true_gain.reshape(-1, 1)]
    else:
        feature_names = ZHAT_TIER_DEFINITIONS[tier]
        Z_parts = []
        for fname in feature_names:
            if fname == "amplitude":
                Z_parts.append(dataset["amplitude"].reshape(-1, 1))
            elif fname == "timing_hat":
                assert timing_hat is not None, "Zhat-2 requires timing_hat (see estimate_timing_nested)"
                # P2 (2026-08-29): reject a mismatched-seed pairing rather than silently
                # evaluating a timing estimate that was cross-fit against a DIFFERENT partition
                # than the one about to be used -- that breaks the cross-fitting guarantee with
                # no visible symptom. Estimates produced before this tagging (or by a caller
                # supplying a plain ndarray) carry no fingerprint and are passed through, so
                # this is additive, not a breaking change.
                expected = getattr(timing_hat, "folds_fingerprint", None)
                if expected is not None:
                    actual = folds_fingerprint(len(y), n_splits, seed)
                    if expected != actual:
                        raise ValueError(
                            "timing_hat was cross-fit against a different CV partition than this "
                            f"evaluation uses (timing_hat folds={expected}, "
                            f"fit_nuisance_tier folds={actual} for n_splits={n_splits}, seed={seed}). "
                            "Pass the SAME n_splits and seed to estimate_timing_nested and "
                            "fit_nuisance_tier; otherwise the cross-fitting guarantee is void."
                        )
                Z_parts.append(np.asarray(timing_hat).reshape(-1, 1))
        if extra_Z:
            Z_parts.extend([z.reshape(-1, 1) for z in extra_Z])

    X_M1 = own_hist
    X_M2 = np.hstack([X_M1] + Z_parts) if Z_parts else X_M1
    X_M3 = np.hstack([X_M2, lag])

    r2_M1 = _held_out_r2(X_M1, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M2 = _held_out_r2(X_M2, y, n_splits=n_splits, alpha=alpha, seed=seed)
    r2_M3 = _held_out_r2(X_M3, y, n_splits=n_splits, alpha=alpha, seed=seed)
    return {"tier": tier, "r2_M1": r2_M1, "r2_M2": r2_M2, "r2_M3": r2_M3, "delta": r2_M3 - r2_M2}


def integrated_lag_coefficients(dataset: dict, *, alpha: float = 1.0) -> dict:
    """Fit M3 on the FULL data (no held-out split -- this is a descriptive coefficient summary,
    not the primary inferential statistic) and report the signed coefficient per lag bin, after
    standardization, so bin-to-bin comparison is meaningful. tau* (argmax |coef|) is reported only
    as a SECONDARY descriptive statistic per Hamm's explicit instruction -- the coefficient
    trajectory is the primary distributed-lag output."""
    y = dataset["outcome"]
    own_hist = dataset["own_history"].reshape(-1, 1)
    amp = dataset["amplitude"].reshape(-1, 1)
    timing = dataset["timing"].reshape(-1, 1)
    lag = dataset["lag_features"]
    X = np.hstack([own_hist, amp, timing, lag])
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    model = Ridge(alpha=alpha).fit(Xs, y)
    lag_coefs = model.coef_[3:]  # own_hist, amp, timing are the first 3 columns
    bins = dataset["lag_bins_ms"]
    peak_idx = int(np.argmax(np.abs(lag_coefs)))
    return {
        "lag_bin_coefficients": {f"{lo}-{hi}ms": float(c) for (lo, hi), c in zip(bins, lag_coefs)},
        "integrated_coefficient_mass": float(np.sum(lag_coefs)),
        "sign_of_integrated_mass": "positive" if np.sum(lag_coefs) > 0 else "negative",
        "tau_star_secondary_descriptive": f"{bins[peak_idx][0]}-{bins[peak_idx][1]}ms",
    }
