"""omission.jnwb_ext.common_driver_control -- controls for the shared-event-jitter confound.

2026-08-28 (Hamm). The adversarial test in omission/tests/test_adversarial_shared_event_null.py
established that ordinary within-condition trial-shuffle permutation gives a 100% false-positive
rate (10/10 seeds) when P (LFP proxy) and R (spike proxy) share a per-trial timing jitter E_i
that shifts BOTH signals' response kernels together, with ZERO direct P->R coupling. This module
implements and adversarially validates candidate controls against exactly that confound, before
any real-data P4 directionality claim is attempted.

Generative model under test (see synthesize_adversarial_pair):
    E_i ~ N(0, jitter_sd_ms)                          per-trial shared timing jitter
    P_i(t) = kernel(t; p_center + E_i, p_sigma) + noise
    R_i(t) = kernel(t; r_center + E_i, r_sigma)
             + coupling_strength * kernel(t; p_center + E_i + coupling_lag_ms, p_sigma)  [optional]
             + noise
E_i is UNOBSERVED. coupling_strength=0 is the negative control (defeated trial-shuffle); >0 is
the positive control (genuine P->R coupling on top of the SAME confound) -- a valid method must
reject the former and recover the latter's coupling_lag_ms.

Two candidate controls are implemented and benchmarked against both controls:

  A. event_template_residualize -- cross-validated group-average template subtraction (removes
     the across-trial MEAN evoked shape, estimated on a held-out fold). Included as a natural
     first idea but expected, and confirmed below, to be insufficient: it only removes the
     average template locked to the OBSERVED/nominal event time, not each trial's own hidden
     jitter deviation from that average -- so shared-jitter-driven correlation is expected to
     survive in the residuals.

  B. reference_peak_realign -- per-trial realignment using an estimate of E_i extracted from P
     alone (P's own peak time is a valid proxy for E_i in BOTH the null and alternative
     generative models, since P's generation never depends on R by construction -- so this does
     not introduce circularity the way estimating E_i from R, or from both jointly, would).
     After realigning both P and R by the SAME per-trial estimated shift, the shared-jitter
     component of R's kernel is removed (to first order, limited by the peak-detector's own
     noise), while a genuine P->R coupling term -- which by construction rides on P's own
     realized (jittered) trace, not on the estimate of E_i itself -- survives realignment
     because P and its coupling-driven R component share the exact SAME realized jitter and
     therefore stay aligned to each other under the SAME shift.
"""
from __future__ import annotations

import numpy as np

from omission.jnwb_ext.lag_estimation import lagged_association
from omission.jnwb_ext.nulls import trial_permutation

FS = 1000.0


def _gaussian_kernel(t, center, sigma):
    return np.exp(-0.5 * ((t - center) / sigma) ** 2)


def synthesize_adversarial_pair(
    n_trials=60, trial_len=400, p_center=150.0, p_sigma=25.0, r_center=220.0, r_sigma=5.0,
    jitter_sd_ms=8.0, coupling_strength=0.0, coupling_lag_ms=30.0, coupling_direction="P_to_R",
    noise_sd=0.3, p_noise_sd=None, r_noise_sd=None, seed=0,
):
    """Returns (P_trials, R_trials, true_jitter) -- true_jitter is returned ONLY for internal
    validation of candidate methods' jitter recovery; no candidate method may use it directly.

    coupling_direction: "P_to_R" (LFP leads spike -- R gets an extra term riding on P's own
    realized trace) or "R_to_P" (spike leads LFP -- P gets an extra term riding on R's own
    realized trace), so both directions can be adversarially benchmarked, not just P->R.

    p_noise_sd/r_noise_sd override noise_sd independently per signal when set (for the
    power/calibration surface's noise sweeps); noise_sd is the shared default for both.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(trial_len)
    p_noise = noise_sd if p_noise_sd is None else p_noise_sd
    r_noise = noise_sd if r_noise_sd is None else r_noise_sd
    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    true_jitter = np.empty(n_trials)
    for i in range(n_trials):
        e_i = rng.normal(0, jitter_sd_ms) if jitter_sd_ms > 0 else 0.0
        true_jitter[i] = e_i
        p_clean = _gaussian_kernel(t, p_center + e_i, p_sigma)
        r_indep = _gaussian_kernel(t, r_center + e_i, r_sigma)
        if coupling_direction == "P_to_R":
            r_coupled = coupling_strength * _gaussian_kernel(t, p_center + e_i + coupling_lag_ms, p_sigma)
            p_coupled = 0.0
        elif coupling_direction == "R_to_P":
            p_coupled = coupling_strength * _gaussian_kernel(t, r_center + e_i + coupling_lag_ms, r_sigma)
            r_coupled = 0.0
        else:
            raise ValueError(f"coupling_direction must be 'P_to_R' or 'R_to_P', got {coupling_direction!r}")
        P_trials[i] = p_clean + p_coupled + rng.normal(0, p_noise, trial_len)
        R_trials[i] = r_indep + r_coupled + rng.normal(0, r_noise, trial_len)
    return P_trials, R_trials, true_jitter


# -------------------------------------------------------------------------------------------
# Candidate A: cross-validated event-template residualization
# -------------------------------------------------------------------------------------------

def event_template_residualize(P_trials: np.ndarray, R_trials: np.ndarray, n_folds: int = 5, seed: int = 0):
    """Subtract the across-trial MEAN template from each trial, template estimated on a
    held-out fold (never the trial's own fold) to avoid the trivial 'residual is exactly zero
    for its own contribution to the mean' leakage. Does NOT use any per-trial timing estimate --
    only the group-average shape locked to the nominal (jitter-free) trial time axis."""
    n_trials = P_trials.shape[0]
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, n_folds, size=n_trials)
    P_resid = np.empty_like(P_trials)
    R_resid = np.empty_like(R_trials)
    for f in range(n_folds):
        test_idx = fold == f
        train_idx = ~test_idx
        if not test_idx.any() or not train_idx.any():
            continue
        p_template = P_trials[train_idx].mean(axis=0)
        r_template = R_trials[train_idx].mean(axis=0)
        P_resid[test_idx] = P_trials[test_idx] - p_template
        R_resid[test_idx] = R_trials[test_idx] - r_template
    return P_resid, R_resid


# -------------------------------------------------------------------------------------------
# Candidate B: reference-peak realignment (jitter estimated from P alone)
# -------------------------------------------------------------------------------------------

def _estimate_trial_peak_time(trial: np.ndarray, search_window: tuple[float, float] | None = None) -> float:
    n = len(trial)
    if search_window is None:
        lo, hi = 0, n
    else:
        lo, hi = int(max(0, search_window[0])), int(min(n, search_window[1]))
    seg = trial[lo:hi]
    return float(lo + np.argmax(seg))


def reference_peak_realign(P_trials: np.ndarray, R_trials: np.ndarray, *, p_search_window=None,
                            max_shift: int = 60):
    """Estimate each trial's own timing offset from P ALONE via raw argmax (P never depends on
    R by construction, in either the null or coupled generative model, so referencing off P
    cannot introduce circularity), then realign BOTH P and R in that trial by the same
    integer-sample shift.

    CAUTION (found 2026-08-28 during this control's own adversarial validation): raw argmax is a
    poor localizer for a broad, low-curvature kernel under realistic noise -- empirically its own
    estimation error (SD~13ms here) EXCEEDED the true jitter it was meant to remove (SD=8ms),
    so this naive version does not actually fix the negative control (see
    matched_filter_peak_realign for the estimator that does). Kept here, not deleted, because the
    comparison between the two is itself the receipted evidence for why estimator precision
    matters, not just the realignment idea's logic.
    """
    n_trials, trial_len = P_trials.shape
    ref_time = float(np.median([_estimate_trial_peak_time(P_trials[i], p_search_window) for i in range(n_trials)]))
    P_aligned = np.empty_like(P_trials)
    R_aligned = np.empty_like(R_trials)
    shifts = np.empty(n_trials, dtype=int)
    for i in range(n_trials):
        t_i = _estimate_trial_peak_time(P_trials[i], p_search_window)
        shift = int(np.clip(round(ref_time - t_i), -max_shift, max_shift))
        shifts[i] = shift
        P_aligned[i] = np.roll(P_trials[i], shift)
        R_aligned[i] = np.roll(R_trials[i], shift)
    return P_aligned, R_aligned, shifts


def _matched_filter_lag(trial: np.ndarray, template: np.ndarray, max_shift: int) -> int:
    """Cross-correlate ``trial`` against ``template`` and return the integer shift (samples)
    that best aligns template to trial, restricted to +/-max_shift -- far more noise-robust than
    single-sample argmax because it uses every sample of the template's shape, not just the
    single noisiest point at the peak."""
    n = len(trial)
    template = template - template.mean()
    trial_c = trial - trial.mean()
    best_shift, best_score = 0, -np.inf
    for shift in range(-max_shift, max_shift + 1):
        shifted = np.roll(template, shift)
        score = float(np.dot(shifted, trial_c))
        if score > best_score:
            best_score, best_shift = score, shift
    return best_shift


def matched_filter_peak_realign(P_trials: np.ndarray, R_trials: np.ndarray, *, n_folds: int = 5,
                                 max_shift: int = 60, seed: int = 0):
    """Same logic as reference_peak_realign (estimate each trial's timing offset from P alone,
    apply the SAME shift to both P and R), but the per-trial timing estimate is a matched-filter
    cross-correlation against a cross-validated group-average P template (fold-held-out, same
    discipline as event_template_residualize) instead of raw single-sample argmax -- built after
    reference_peak_realign's own adversarial validation showed argmax's estimation error (SD~13ms)
    exceeded the jitter it needed to remove (SD=8ms).
    """
    n_trials, trial_len = P_trials.shape
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, n_folds, size=n_trials)

    shifts = np.empty(n_trials, dtype=int)
    for f in range(n_folds):
        test_idx = np.flatnonzero(fold == f)
        train_idx = np.flatnonzero(fold != f)
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        template = P_trials[train_idx].mean(axis=0)
        for i in test_idx:
            shifts[i] = _matched_filter_lag(P_trials[i], template, max_shift)

    # shifts[i] ~= trial i's own jitter e_i relative to the (zero-jitter-on-average) template
    # (np.roll(template, shifts[i]) best matches trial i). To CANCEL that jitter -- moving the
    # trial's own kernel back to the common reference position -- roll the TRIAL by -shifts[i]
    # (plus ref_shift to correct for the template average's own small residual offset).
    ref_shift = int(round(np.median(shifts)))
    P_aligned = np.empty_like(P_trials)
    R_aligned = np.empty_like(R_trials)
    for i in range(n_trials):
        s = ref_shift - shifts[i]
        P_aligned[i] = np.roll(P_trials[i], s)
        R_aligned[i] = np.roll(R_trials[i], s)
    return P_aligned, R_aligned, shifts


# -------------------------------------------------------------------------------------------
# Candidate C: timing-conditioned (matched) permutation null
# -------------------------------------------------------------------------------------------

def estimate_nuisance_bins(P_trials: np.ndarray, *, n_bins: int = 4, n_folds: int = 5, seed: int = 0):
    """Per-trial nuisance-covariate estimate (matched-filter jitter proxy from P alone, same
    validated CV estimator as Candidate B2) binned into n_bins quantile bins for matched
    permutation. Real-data use would concatenate this with condition/position/cycle/history
    covariates before binning -- in this synthetic benchmark only jitter varies, so it is the
    sole nuisance dimension available to condition on, by construction of the adversarial
    generator itself.
    """
    n_trials, trial_len = P_trials.shape
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, n_folds, size=n_trials)
    shifts = np.empty(n_trials)
    for f in range(n_folds):
        test_idx = np.flatnonzero(fold == f)
        train_idx = np.flatnonzero(fold != f)
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        template = P_trials[train_idx].mean(axis=0)
        for i in test_idx:
            shifts[i] = _matched_filter_lag(P_trials[i], template, max_shift=60)
    ranks = np.argsort(np.argsort(shifts))
    bins = np.clip((ranks * n_bins) // n_trials, 0, n_bins - 1)
    return shifts, bins


def matched_permutation_pvalue(P_trials: np.ndarray, R_trials: np.ndarray, *, n_bins: int = 4,
                                n_perm: int = 200, seed: int = 0):
    """Candidate C: bin trials by estimated nuisance timing state, then permute R's trial
    assignment ONLY WITHIN each bin (reusing the already-validated trial_permutation/
    permute_labels(scheme='within_group') machinery with the bin id as the group key). Applied
    to the RAW (unaligned) P/R -- unlike B2, this does NOT shift/realign any trial's own signal,
    so it does not pay B2's realignment-estimation-noise power cost; instead it destroys only
    the SPECIFIC trial-to-trial pairing (any residual coupling beyond what's explained by the
    matched nuisance state) while approximately preserving each bin's own shared-timing-driven
    correlation structure (event timing -> P, event timing -> R both stay intact WITHIN a bin,
    since bin membership means similar estimated jitter).
    """
    n_trials = P_trials.shape[0]
    shifts, bins = estimate_nuisance_bins(P_trials, n_bins=n_bins, seed=seed)
    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS)
    observed_peak = np.nanmax(np.abs(C_obs))
    observed_lag = LAGS_MS[np.nanargmax(np.abs(C_obs))]

    null_peaks = np.empty(n_perm)
    for k in range(n_perm):
        order = trial_permutation(np.arange(n_trials), condition_position_group=bins,
                                   rng=np.random.default_rng(seed + 100000 + k))
        R_shuffled = R_trials[order].reshape(-1)
        Cn = lagged_association(P_concat, R_shuffled, LAGS_MS, fs=FS)
        null_peaks[k] = np.nanmax(np.abs(Cn))

    p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
    bin_counts = np.bincount(bins, minlength=n_bins)
    return {"p": p, "observed_peak": observed_peak, "observed_lag_ms": observed_lag,
            "null_mean": float(null_peaks.mean()), "null_sd": float(null_peaks.std()),
            "bin_counts": bin_counts.tolist(), "n_bins": n_bins}


# -------------------------------------------------------------------------------------------
# Shared benchmark harness
# -------------------------------------------------------------------------------------------

# -------------------------------------------------------------------------------------------
# General adversarial generator (2026-08-28, Hamm's expanded confound battery) + Candidate
# C-multivariate: nuisance-matched permutation using a SAFE (pre-event) amplitude/gain covariate
# alongside the timing covariate, not just timing alone.
# -------------------------------------------------------------------------------------------

def synthesize_general_adversarial_pair(
    n_trials=60, trial_len=400, baseline_window=(0, 80),
    p_center=150.0, p_sigma=25.0, r_center=220.0, r_sigma=5.0,
    jitter_sd_ms=0.0, amp_gain=0.0, amp_phi=0.95,
    coupling_strength=0.0, coupling_lag_ms=30.0, coupling_direction="P_to_R",
    kernel_width_jitter_sd=0.0, baseline_amp=0.15,
    noise_sd=0.3, p_noise_sd=None, r_noise_sd=None, seed=0,
):
    """General confound generator: shared timing jitter (E_i) and/or shared amplitude/gain
    co-modulation (AR(1) latent state z_i across TRIAL INDEX, autocorrelation amp_phi) can be
    turned on independently, plus optional true coupling and trial-varying kernel width.

    Variable-safety design (Hamm, 2026-08-28 item 1/2): an EXPLICIT low-amplitude baseline
    segment is added in ``baseline_window`` (default samples 0-80, well before p_center=150
    minus 3*p_sigma=75 -- i.e. strictly PRE-EVENT for any plausible coupling_lag_ms), scaled by
    the SAME gain state z_i that scales the post-event kernel amplitude. This baseline segment is
    a genuine pre-existing/design-time signal component: because every coupling term (in either
    direction) is constructed to occur AT OR AFTER p_center/r_center, the baseline window is
    structurally incapable of reflecting a consequence of the hypothesized coupling -- it is a
    safe common-cause proxy for the gain confound, not a mediator or outcome. Estimating a gain
    covariate from THIS segment (see estimate_amplitude_covariate) is the safe analogue of using
    P's own peak TIME (never touched by coupling) as the safe timing covariate.

    coupling_direction="R_to_P" now uses p_sigma (not r_sigma) for its coupling kernel width --
    matching P_to_R's use of p_sigma -- so injected coupling energy/width is symmetric between
    directions (Hamm item 7; the prior asymmetric version used r_sigma, confounding the reverse
    direction with the r_center/p_center baseline-offset artifact).

    Returns (P_trials, R_trials, true_jitter, true_gain) -- both ground-truth arrays are for
    internal validation only; no candidate method may use them.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(trial_len)
    p_noise = noise_sd if p_noise_sd is None else p_noise_sd
    r_noise = noise_sd if r_noise_sd is None else r_noise_sd

    z = np.zeros(n_trials)
    if amp_gain != 0.0:
        z[0] = rng.normal(0, 1)
        for i in range(1, n_trials):
            z[i] = amp_phi * z[i - 1] + rng.normal(0, np.sqrt(max(1 - amp_phi ** 2, 1e-9)))

    lo, hi = baseline_window
    baseline_shape = np.zeros(trial_len)
    baseline_shape[lo:hi] = 1.0

    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    true_jitter = np.empty(n_trials)
    true_gain = np.empty(n_trials)

    for i in range(n_trials):
        e_i = rng.normal(0, jitter_sd_ms) if jitter_sd_ms > 0 else 0.0
        true_jitter[i] = e_i
        gain = 1.0 + amp_gain * z[i]
        true_gain[i] = gain

        if kernel_width_jitter_sd > 0:
            p_sigma_i = max(p_sigma * (1 + rng.normal(0, kernel_width_jitter_sd)), 1.0)
            r_sigma_i = max(r_sigma * (1 + rng.normal(0, kernel_width_jitter_sd)), 1.0)
        else:
            p_sigma_i, r_sigma_i = p_sigma, r_sigma

        p_clean = gain * _gaussian_kernel(t, p_center + e_i, p_sigma_i)
        r_indep = gain * _gaussian_kernel(t, r_center + e_i, r_sigma_i)
        if coupling_direction == "P_to_R":
            r_coupled = coupling_strength * _gaussian_kernel(t, p_center + e_i + coupling_lag_ms, p_sigma_i)
            p_coupled = 0.0
        elif coupling_direction == "R_to_P":
            p_coupled = coupling_strength * _gaussian_kernel(t, r_center + e_i + coupling_lag_ms, p_sigma_i)
            r_coupled = 0.0
        else:
            raise ValueError(f"coupling_direction must be 'P_to_R' or 'R_to_P', got {coupling_direction!r}")

        p_base = baseline_amp * gain * baseline_shape
        r_base = baseline_amp * gain * baseline_shape

        P_trials[i] = p_clean + p_coupled + p_base + rng.normal(0, p_noise, trial_len)
        R_trials[i] = r_indep + r_coupled + r_base + rng.normal(0, r_noise, trial_len)

    return P_trials, R_trials, true_jitter, true_gain


def degenerate_common_cause_mediated_positive_control(*args, **kwargs):
    """ALIAS of synthesize_general_adversarial_pair, kept under this explicit name (2026-08-28,
    Hamm) as a documented regression case, not a live positive control.

    STRUCTURAL DEGENERACY (found 2026-08-28, see distributed-lag-structured-timing-20260828.json):
    this generator's coupling term,
        r_coupled(t) = coupling_strength * gaussian_kernel(t, p_center + e_i + coupling_lag_ms, p_sigma)
    is a deterministic function of the shared nuisance e_i ALONE -- it never depends on P's
    actually realized (noisy, trial-specific) trace. Consequently ANY conditioning strategy
    flexible enough to null the shared-jitter confound (quadratic-in-e_i and richer, including
    the exact analytic translated-template oracle) ALSO nulls this "coupling" term, since both
    are smooth functions of the identical scalar e_i and are therefore observationally
    indistinguishable given e_i alone.

    This is EXPECTED, CORRECT behavior for a valid conditional estimator, not a power failure --
    see test_degenerate_positive_control_regression.py, which pins D -> 0 under quadratic timing
    conditioning as the required regression behavior. Do not use this generator to claim a
    conditional estimator has "no power" against genuine realized-P->R coupling; for that, use
    omission.jnwb_ext.realized_coupling_generator.synthesize_realized_coupling_pair, whose
    coupling term is constructed from P's actually realized trial-specific innovation (PC1) or
    full realized trace (PC2), never from e_i alone.
    """
    return synthesize_general_adversarial_pair(*args, **kwargs)


def estimate_amplitude_covariate(P_trials: np.ndarray, baseline_window: tuple[int, int] = (0, 80)) -> np.ndarray:
    """Safe gain/amplitude proxy: mean P amplitude in the PRE-EVENT baseline window alone. Never
    touches R, and the window is structurally prior to any coupling term by construction of
    synthesize_general_adversarial_pair -- see that function's docstring for the safety argument.
    """
    lo, hi = baseline_window
    return P_trials[:, lo:hi].mean(axis=1)


def estimate_nuisance_vector(P_trials: np.ndarray, *, baseline_window=(0, 80), timing_n_folds=5,
                              seed=0) -> np.ndarray:
    """z_i = [timing_estimate, amplitude_estimate], both derived from P alone (never R), both
    z-scored so a Euclidean/caliper distance in this space treats both dimensions comparably."""
    shifts, _ = estimate_nuisance_bins(P_trials, n_bins=2, n_folds=timing_n_folds, seed=seed)
    amp = estimate_amplitude_covariate(P_trials, baseline_window)
    z = np.stack([shifts, amp], axis=1).astype(float)
    z = (z - z.mean(axis=0)) / (z.std(axis=0) + 1e-12)
    return z


def multivariate_stratified_bins(z: np.ndarray, n_bins_per_dim: int = 3) -> np.ndarray:
    """Cartesian-product quantile stratification across every column of z -- the multivariate
    extension of estimate_nuisance_bins' single-dimension quantile binning."""
    n_trials, n_dims = z.shape
    dim_bins = np.zeros((n_trials, n_dims), dtype=int)
    for d in range(n_dims):
        ranks = np.argsort(np.argsort(z[:, d]))
        dim_bins[:, d] = np.clip((ranks * n_bins_per_dim) // n_trials, 0, n_bins_per_dim - 1)
    strata = dim_bins[:, 0].copy()
    for d in range(1, n_dims):
        strata = strata * n_bins_per_dim + dim_bins[:, d]
    return strata


def multivariate_matched_permutation_pvalue(P_trials, R_trials, *, z=None, n_bins_per_dim=3,
                                             n_perm=200, seed=0, baseline_window=(0, 80)):
    """Candidate C-multivariate (stratified variant): identical logic to matched_permutation_pvalue
    but strata are the CARTESIAN PRODUCT of quantile bins across every nuisance dimension in z
    (default: [timing, amplitude]), not timing alone."""
    if z is None:
        z = estimate_nuisance_vector(P_trials, baseline_window=baseline_window, seed=seed)
    n_trials = P_trials.shape[0]
    strata = multivariate_stratified_bins(z, n_bins_per_dim=n_bins_per_dim)
    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS)
    observed_peak = np.nanmax(np.abs(C_obs))
    observed_lag = LAGS_MS[np.nanargmax(np.abs(C_obs))]

    null_peaks = np.empty(n_perm)
    for k in range(n_perm):
        order = trial_permutation(np.arange(n_trials), condition_position_group=strata,
                                   rng=np.random.default_rng(seed + 200000 + k))
        R_shuffled = R_trials[order].reshape(-1)
        Cn = lagged_association(P_concat, R_shuffled, LAGS_MS, fs=FS)
        null_peaks[k] = np.nanmax(np.abs(Cn))

    p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
    strata_counts = np.bincount(strata)
    return {"p": p, "observed_peak": observed_peak, "observed_lag_ms": observed_lag,
            "null_mean": float(null_peaks.mean()), "null_sd": float(null_peaks.std()),
            "n_strata_used": int((strata_counts > 0).sum()), "strata_counts": strata_counts.tolist()}


def caliper_matched_permutation_pvalue(P_trials, R_trials, *, z=None, caliper=1.0, n_perm=200,
                                        seed=0, baseline_window=(0, 80), swap_attempts_factor=6,
                                        balance_reject_threshold=None, max_redraws=5):
    """Candidate C-multivariate (caliper variant): a null draw is built via repeated RESTRICTED
    random transpositions -- sample a random trial pair (i,j); swap their R assignment only if
    the standardized Euclidean nuisance distance ||z_i - z_j|| <= caliper; repeat for a budget of
    ``swap_attempts_factor * n_trials`` attempts. This is a valid permutation (a product of
    disjoint transpositions, each respecting the caliper) by construction, unlike quantile
    stratification it does not require choosing a bin count and degrades gracefully as caliper
    shrinks (fewer trials get swapped, closer to the identity permutation -- reported via
    n_pairs_swapped, not silently).

    Balance diagnostic (Hamm item 3): for each realized null draw, compute the standardized
    nuisance difference between every swapped pair, averaged -- if it exceeds
    ``balance_reject_threshold`` the draw is discarded and redrawn (up to max_redraws) rather
    than accepted as if the swap were exchangeable. balance_mean_per_draw is returned so this can
    be audited even when no threshold is set (None disables rejection, diagnostic-only mode).
    """
    if z is None:
        z = estimate_nuisance_vector(P_trials, baseline_window=baseline_window, seed=seed)
    n_trials = P_trials.shape[0]
    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS)
    observed_peak = np.nanmax(np.abs(C_obs))
    observed_lag = LAGS_MS[np.nanargmax(np.abs(C_obs))]

    def _draw_once(rng):
        order = np.arange(n_trials)
        swapped_pairs = []
        n_attempts = int(swap_attempts_factor * n_trials)
        for _ in range(n_attempts):
            i, j = rng.integers(0, n_trials, size=2)
            if i == j:
                continue
            dist = float(np.linalg.norm(z[i] - z[j]))
            if dist <= caliper:
                order[i], order[j] = order[j], order[i]
                swapped_pairs.append(dist)
        return order, swapped_pairs

    null_peaks = np.empty(n_perm)
    balance_per_draw = np.full(n_perm, np.nan)
    n_pairs_per_draw = np.zeros(n_perm, dtype=int)
    for k in range(n_perm):
        rng = np.random.default_rng(seed + 300000 + k)
        for attempt in range(max_redraws):
            order, swapped_pairs = _draw_once(rng)
            balance = float(np.mean(swapped_pairs)) if swapped_pairs else 0.0
            if balance_reject_threshold is None or balance <= balance_reject_threshold or attempt == max_redraws - 1:
                break
        balance_per_draw[k] = balance
        n_pairs_per_draw[k] = len(swapped_pairs)
        R_shuffled = R_trials[order].reshape(-1)
        Cn = lagged_association(P_concat, R_shuffled, LAGS_MS, fs=FS)
        null_peaks[k] = np.nanmax(np.abs(Cn))

    p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
    return {"p": p, "observed_peak": observed_peak, "observed_lag_ms": observed_lag,
            "null_mean": float(null_peaks.mean()), "null_sd": float(null_peaks.std()),
            "mean_balance": float(np.nanmean(balance_per_draw)),
            "mean_n_pairs_swapped": float(n_pairs_per_draw.mean())}


LAGS_MS = np.arange(-150, 151, 1.0)


def trial_shuffle_pvalue(P_trials: np.ndarray, R_trials: np.ndarray, n_perm: int = 200, seed: int = 100):
    n_trials = P_trials.shape[0]
    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS)
    observed_peak = np.nanmax(np.abs(C_obs))
    observed_lag = LAGS_MS[np.nanargmax(np.abs(C_obs))]

    condition_group = np.zeros(n_trials, dtype=int)
    null_peaks = np.empty(n_perm)
    for k in range(n_perm):
        order = trial_permutation(np.arange(n_trials), condition_position_group=condition_group,
                                   rng=np.random.default_rng(seed + k))
        R_shuffled = R_trials[order].reshape(-1)
        Cn = lagged_association(P_concat, R_shuffled, LAGS_MS, fs=FS)
        null_peaks[k] = np.nanmax(np.abs(Cn))

    p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
    return {"p": p, "observed_peak": observed_peak, "observed_lag_ms": observed_lag,
            "null_mean": float(null_peaks.mean()), "null_sd": float(null_peaks.std())}
