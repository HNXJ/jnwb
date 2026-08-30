"""omission.jnwb_ext.realized_coupling_generator -- structurally valid P->R positive control.

2026-08-28 (Hamm). The prior adversarial generator's positive control
(`synthesize_general_adversarial_pair` / `common_driver_control.py`) was found to be
STRUCTURALLY DEGENERATE for testing conditional identification of directed predictive coupling:
its coupling term

    r_coupled(t) = coupling_strength * gaussian_kernel(t, p_center + e_i + coupling_lag_ms, p_sigma)

is a deterministic function of the shared nuisance e_i ALONE -- it does not depend on P's actually
realized (noisy, trial-specific) trace at all. Consequently any conditioning strategy flexible
enough to null the shared-jitter confound (quadratic+ in e_i; see
distributed-lag-structured-timing-20260828.json) ALSO nulls the "coupling" term, since both are
smooth functions of the identical scalar e_i and therefore observationally indistinguishable given
e_i. That generator is preserved unmodified (see
common_driver_control.degenerate_common_cause_mediated_positive_control) as a documented
regression case: a correct conditional method SHOULD remove this effect, and its removal is not a
power failure.

This module builds a structurally valid alternative in which the tested exposure -- P's own
realized trajectory -- carries information beyond the shared nuisance state, and only THAT private
information is permitted to drive R in the positive control:

    Z_i = (e_i, a_i)                                    shared nuisance (timing jitter, gain)
    P_shared_i(t)  = a_i * kernel(t; p_center+e_i, p_sigma)      Z -> P edge
    P_private_i(t) = rho * smooth_noise_i(t)             independent per-trial innovation, NOT a
                                                          function of Z (own RNG stream)
    P_i(t)         = P_shared_i(t) + P_private_i(t) + measurement_noise

    R_shared_i(t)  = a_i * kernel(t; r_center+e_i, r_sigma)      Z -> R edge (same nuisance)
    coupling_i(t)  = beta * causal_shift(X_i, delay_ms)          P -> R edge, POSITIVE CONTROL ONLY
        X_i = P_private_i         (PC1, "innovation coupling" -- default, most diagnostic:
                                    the transmitted signal is explicit and cannot be reconstructed
                                    from Z by construction)
        X_i = P_shared_i+P_private_i   (PC2, "realized coupling" -- harder: shared and private
                                    components coexist in the transmitted signal, more
                                    physiologically analogous)
    R_i(t)         = R_shared_i(t) + coupling_i(t) + measurement_noise

beta=0 is the negative control: Z -> {P,R} with NO P -> R edge (P_private exists and varies R
only through the shared Z->R edge's own independent noise, never through coupling_i). beta>0 is
the positive control: the SAME Z->{P,R} structure plus a genuine, realized-trace-dependent P->R
edge. This is the exact distinction a valid conditional-predictive estimator must recover.

RNG streams are DELIBERATELY separated (z_seed for Z, private_seed for P_private/measurement
noise) so callers can hold Z fixed while varying only the private/innovation draw -- required for
the replay/intervention generator test (test_realized_coupling_generator.py, Test 3).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d

from omission.jnwb_ext.common_driver_control import _gaussian_kernel

FS = 1000.0


def _causal_shift(x: np.ndarray, delay_samples: int) -> np.ndarray:
    """Shift x forward in time by delay_samples (zero-filled at the start), i.e.
    out[t] = x[t - delay_samples] for t >= delay_samples, else 0. A genuinely CAUSAL delay: no
    information from x[t] or later can appear in out[t' <= t]."""
    if delay_samples <= 0:
        return x.copy()
    out = np.zeros_like(x)
    if delay_samples < len(x):
        out[delay_samples:] = x[: len(x) - delay_samples]
    return out


def _make_private_waveform(rng: np.random.Generator, trial_len: int, rho: float, smooth_sigma: float) -> np.ndarray:
    """Smooth, zero-mean, unit-scale-normalized colored noise -- the per-trial 'innovation' that
    is NOT a function of any shared nuisance variable (own independent draw). Normalizing each
    trial's raw waveform by its own std before scaling by rho keeps rho interpretable as a
    consistent amplitude scale across trials/seeds, rather than being confounded with per-trial
    noise-realization variance."""
    if rho == 0.0:
        return np.zeros(trial_len)
    white = rng.normal(0, 1, trial_len)
    smoothed = gaussian_filter1d(white, sigma=smooth_sigma)
    smoothed = smoothed / (smoothed.std() + 1e-12)
    return rho * smoothed


def synthesize_realized_coupling_pair(
    n_trials: int = 60, trial_len: int = 400, baseline_window=(0, 80),
    p_center: float = 150.0, p_sigma: float = 25.0, r_center: float = 220.0, r_sigma: float = 5.0,
    jitter_sd_ms: float = 0.0, amp_gain: float = 0.0, amp_phi: float = 0.95,
    rho: float = 0.3, private_smooth_sigma: float = 8.0,
    beta: float = 0.0, delay_ms: float = 30.0, coupling_kind: str = "innovation",
    baseline_amp: float = 0.15, noise_sd: float = 0.3, p_noise_sd: float | None = None,
    r_noise_sd: float | None = None, true_jitter: np.ndarray | None = None,
    true_gain: np.ndarray | None = None, z_seed: int = 0, private_seed: int = 1,
):
    """Returns (P_trials, R_trials, true_jitter, true_gain, P_private) -- P_private is returned
    ONLY for generator-level verification (Test 1-4 below); no candidate estimator may use it.

    coupling_kind: "innovation" (PC1, X_i = P_private_i -- default) or "realized" (PC2,
    X_i = P_shared_i + P_private_i).

    z_seed/private_seed are SEPARATE RNG streams by design: passing the same z_seed with
    different private_seed values holds the nuisance realization (e_i, a_i) fixed while varying
    only the private/innovation draw -- the replay/intervention test's exact requirement.
    Pass explicit true_jitter/true_gain arrays to bypass z_seed generation entirely (used by the
    replay test to guarantee bit-identical Z across two calls).
    """
    rng_z = np.random.default_rng(z_seed)
    rng_priv = np.random.default_rng(private_seed)
    t = np.arange(trial_len)
    p_noise = noise_sd if p_noise_sd is None else p_noise_sd
    r_noise = noise_sd if r_noise_sd is None else r_noise_sd

    if true_jitter is None:
        true_jitter = rng_z.normal(0, jitter_sd_ms, n_trials) if jitter_sd_ms > 0 else np.zeros(n_trials)
    if true_gain is None:
        z_latent = np.zeros(n_trials)
        if amp_gain != 0.0:
            z_latent[0] = rng_z.normal(0, 1)
            for i in range(1, n_trials):
                z_latent[i] = amp_phi * z_latent[i - 1] + rng_z.normal(0, np.sqrt(max(1 - amp_phi ** 2, 1e-9)))
        true_gain = 1.0 + amp_gain * z_latent

    lo, hi = baseline_window
    baseline_shape = np.zeros(trial_len)
    baseline_shape[lo:hi] = 1.0
    delay_samples = int(round(delay_ms * FS / 1000.0))

    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    P_private = np.empty((n_trials, trial_len))

    for i in range(n_trials):
        e_i, gain_i = true_jitter[i], true_gain[i]

        p_shared = gain_i * _gaussian_kernel(t, p_center + e_i, p_sigma)
        p_priv = _make_private_waveform(rng_priv, trial_len, rho, private_smooth_sigma)
        P_private[i] = p_priv
        p_base = baseline_amp * gain_i * baseline_shape
        P_trials[i] = p_shared + p_priv + p_base + rng_priv.normal(0, p_noise, trial_len)

        r_shared = gain_i * _gaussian_kernel(t, r_center + e_i, r_sigma)
        if beta > 0:
            source = p_priv if coupling_kind == "innovation" else (p_shared + p_priv)
            coupling = beta * _causal_shift(source, delay_samples)
        else:
            coupling = 0.0
        r_base = baseline_amp * gain_i * baseline_shape
        R_trials[i] = r_shared + coupling + r_base + rng_priv.normal(0, r_noise, trial_len)

    return P_trials, R_trials, true_jitter, true_gain, P_private


def synthesize_bidirectional_coupling_pair(
    n_trials: int = 60, trial_len: int = 400, baseline_window=(0, 80),
    p_center: float = 150.0, p_sigma: float = 25.0, r_center: float = 220.0, r_sigma: float = 5.0,
    jitter_sd_ms: float = 0.0, amp_gain: float = 0.0, amp_phi: float = 0.95,
    rho: float = 0.3, private_smooth_sigma: float = 8.0,
    beta_p_to_r: float = 0.0, beta_r_to_p: float = 0.0, delay_ms: float = 30.0,
    coupling_kind: str = "realized", baseline_amp: float = 0.15, noise_sd: float = 0.3,
    p_noise_sd: float | None = None, r_noise_sd: float | None = None,
    true_jitter: np.ndarray | None = None, true_gain: np.ndarray | None = None,
    z_seed: int = 0, private_seed: int = 1,
):
    """2026-08-28 (Hamm), reverse-direction / bidirectional extension. Independently draws BOTH
    P_private AND R_private (same rho, same private_smooth_sigma, independent RNG sub-streams --
    hence identically DISTRIBUTED, satisfying 'match private innovation variance' and 'match
    kernel width' [the smoothing kernel used to build each private waveform, NOT p_sigma/r_sigma,
    which are separate, unchanged signal identities] by construction). P_shared/R_shared keep
    their own natural centers/widths (p_center/p_sigma for P, r_center/r_sigma for R) EXACTLY as
    in the one-directional generator -- nothing about each signal's own identity changes.

    Coupling can be injected in EITHER or BOTH directions simultaneously:
        beta_p_to_r > 0: R += beta_p_to_r * causal_shift(source_from_P, delay_ms)
        beta_r_to_p > 0: P += beta_r_to_p * causal_shift(source_from_R, delay_ms)
    where source_from_X = X_private (coupling_kind='innovation') or X_shared+X_private
    (coupling_kind='realized', the default here per Hamm's 'construct symmetric realized-R->P
    coupling' instruction). This does NOT create a causality paradox even with both directions
    active simultaneously, because both couplings are strictly CAUSAL (delay_ms > 0) and computed
    from each signal's PRE-COUPLING private/shared components, never from the other's post-
    coupling value -- there is no feedback loop, just two independent forward edges Z->P->R and
    Z->R->P (via each other's private/shared material) evaluated in the same generative pass.

    'Match coupling energy' (Hamm) is NOT automatic from equal beta_p_to_r/beta_r_to_p, because
    std(P_shared+P_private) generally differs from std(R_shared+R_private) (different kernel
    widths p_sigma vs r_sigma even though private components match). Use
    calibrate_matched_beta_r_to_p() below to compute a beta_r_to_p that empirically matches
    injected coupling variance to a given beta_p_to_r before calling this function for a
    symmetric comparison -- this function itself applies whatever beta values it is given as-is
    and does not calibrate on its own.

    Returns (P_trials, R_trials, true_jitter, true_gain, P_private, R_private).
    """
    rng_z = np.random.default_rng(z_seed)
    rng_priv = np.random.default_rng(private_seed)
    t = np.arange(trial_len)
    p_noise = noise_sd if p_noise_sd is None else p_noise_sd
    r_noise = noise_sd if r_noise_sd is None else r_noise_sd

    if true_jitter is None:
        true_jitter = rng_z.normal(0, jitter_sd_ms, n_trials) if jitter_sd_ms > 0 else np.zeros(n_trials)
    if true_gain is None:
        z_latent = np.zeros(n_trials)
        if amp_gain != 0.0:
            z_latent[0] = rng_z.normal(0, 1)
            for i in range(1, n_trials):
                z_latent[i] = amp_phi * z_latent[i - 1] + rng_z.normal(0, np.sqrt(max(1 - amp_phi ** 2, 1e-9)))
        true_gain = 1.0 + amp_gain * z_latent

    lo, hi = baseline_window
    baseline_shape = np.zeros(trial_len)
    baseline_shape[lo:hi] = 1.0
    delay_samples = int(round(delay_ms * FS / 1000.0))

    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    P_private = np.empty((n_trials, trial_len))
    R_private = np.empty((n_trials, trial_len))

    for i in range(n_trials):
        e_i, gain_i = true_jitter[i], true_gain[i]
        p_shared = gain_i * _gaussian_kernel(t, p_center + e_i, p_sigma)
        r_shared = gain_i * _gaussian_kernel(t, r_center + e_i, r_sigma)
        p_priv = _make_private_waveform(rng_priv, trial_len, rho, private_smooth_sigma)
        r_priv = _make_private_waveform(rng_priv, trial_len, rho, private_smooth_sigma)
        P_private[i], R_private[i] = p_priv, r_priv

        base = baseline_amp * gain_i * baseline_shape

        coupling_to_r = 0.0
        if beta_p_to_r > 0:
            source_p = p_priv if coupling_kind == "innovation" else (p_shared + p_priv)
            coupling_to_r = beta_p_to_r * _causal_shift(source_p, delay_samples)
        coupling_to_p = 0.0
        if beta_r_to_p > 0:
            source_r = r_priv if coupling_kind == "innovation" else (r_shared + r_priv)
            coupling_to_p = beta_r_to_p * _causal_shift(source_r, delay_samples)

        P_trials[i] = p_shared + p_priv + coupling_to_p + base + rng_priv.normal(0, p_noise, trial_len)
        R_trials[i] = r_shared + r_priv + coupling_to_r + base + rng_priv.normal(0, r_noise, trial_len)

    return P_trials, R_trials, true_jitter, true_gain, P_private, R_private


def calibrate_matched_beta_r_to_p(
    target_beta_p_to_r: float, *, n_calib_trials: int = 500, coupling_kind: str = "realized",
    p_center: float = 150.0, p_sigma: float = 25.0, r_center: float = 220.0, r_sigma: float = 5.0,
    rho: float = 0.3, private_smooth_sigma: float = 8.0, baseline_window=(0, 80),
    baseline_amp: float = 0.15, trial_len: int = 400, calib_seed: int = 999,
) -> dict:
    """Empirically measure std(source_from_P) vs std(source_from_R) (pre-noise, pre-coupling) and
    return a beta_r_to_p such that beta_r_to_p * std(source_R) ~= target_beta_p_to_r *
    std(source_P) -- an energy-matching calibration ('match coupling energy', Hamm), since
    P_shared/R_shared's differing kernel widths (p_sigma vs r_sigma) make raw std(P_shared+
    P_private) != std(R_shared+R_private) even though the private components are identically
    distributed. Uses noise_sd=0, both betas=0 during calibration so the measured std reflects
    only the pre-coupling, pre-noise source material."""
    P, R, true_jitter, true_gain, P_private, R_private = synthesize_bidirectional_coupling_pair(
        n_trials=n_calib_trials, trial_len=trial_len, baseline_window=baseline_window,
        p_center=p_center, p_sigma=p_sigma, r_center=r_center, r_sigma=r_sigma,
        rho=rho, private_smooth_sigma=private_smooth_sigma, beta_p_to_r=0.0, beta_r_to_p=0.0,
        baseline_amp=baseline_amp, noise_sd=0.0, z_seed=calib_seed, private_seed=calib_seed + 1,
    )
    t = np.arange(trial_len)
    if coupling_kind == "innovation":
        source_P = P_private
        source_R = R_private
    else:
        source_P = np.stack([true_gain[i] * _gaussian_kernel(t, p_center + true_jitter[i], p_sigma) for i in range(n_calib_trials)]) + P_private
        source_R = np.stack([true_gain[i] * _gaussian_kernel(t, r_center + true_jitter[i], r_sigma) for i in range(n_calib_trials)]) + R_private
    std_P = float(source_P.std())
    std_R = float(source_R.std())
    beta_r_to_p = target_beta_p_to_r * std_P / std_R
    achieved_std_coupling_P = target_beta_p_to_r * std_P
    achieved_std_coupling_R = beta_r_to_p * std_R
    return {
        "target_beta_p_to_r": target_beta_p_to_r, "calibrated_beta_r_to_p": float(beta_r_to_p),
        "std_source_P": std_P, "std_source_R": std_R,
        "achieved_injected_std_p_to_r": achieved_std_coupling_P,
        "achieved_injected_std_r_to_p": achieved_std_coupling_R,
        "relative_mismatch": abs(achieved_std_coupling_P - achieved_std_coupling_R) / achieved_std_coupling_P,
    }
