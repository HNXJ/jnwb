"""Reusable, deterministic synthetic generators for test infrastructure and tutorials.

This module provides analytically known signals and geometries for testing and calibration
without empirical recording data. All generators accept an explicit RNG/seed and return
known mathematical ground-truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from scipy import signal

from ..addressing import ProbeGeometry, probe_geometry


@dataclass(frozen=True)
class SynthLaminarReceipt:
    """Ground-truth receipt for a synthesized laminar motif recording."""

    lfp: np.ndarray
    fs: float
    crossover_contact: float
    crossover_depth_um: float
    orientation: str
    probe_geometry: ProbeGeometry
    bad_channel_mask: np.ndarray
    pitch_um: float
    gamma_freq: float
    beta_freq: float


def synth_white_noise(
    shape: Union[int, Sequence[int]],
    *,
    scale: float = 1.0,
    mean: float = 0.0,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> np.ndarray:
    """Generate uncorrelated Gaussian white noise with known scale and mean.

    Args:
        shape: Output array dimensions.
        scale: Standard deviation of the noise (must be non-negative).
        mean: Mean of the noise.
        rng: Optional NumPy Generator or integer seed.

    Returns:
        NumPy array of Gaussian white noise with the requested shape.
    """
    scale = float(scale)
    if scale < 0 or not np.isfinite(scale):
        raise ValueError(f"scale must be non-negative and finite, got {scale}")
    gen = np.random.default_rng(rng)
    return gen.normal(loc=float(mean), scale=scale, size=shape)


def synth_ar_noise(
    n_samples: int,
    *,
    n_channels: int = 1,
    tau_s: Optional[float] = None,
    poles: Optional[Sequence[float]] = None,
    fs: float = 1000.0,
    sigma_innov: float = 1.0,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> np.ndarray:
    """Generate stationary autoregressive AR(p) noise with controllable autocorrelation.

    Provides non-white noise preserving temporal persistence and 1/f spectral tilt
    without introducing cross-channel correlation.

    Args:
        n_samples: Number of time samples to generate (must be strictly positive).
        n_channels: Number of independent channels (default 1).
        tau_s: Desired autocorrelation decay time constant in seconds for an AR(1) process:
            ``phi = exp(-1.0 / (fs * tau_s))``. Mutually exclusive with `poles`.
        poles: Explicit AR polynomial coefficients [phi_1, phi_2, ..., phi_p].
            Mutually exclusive with `tau_s`.
        fs: Sampling rate in Hz (default 1000.0).
        sigma_innov: Standard deviation of the white innovation process (default 1.0).
        rng: Optional NumPy Generator or integer seed.

    Returns:
        1D array of shape `(n_samples,)` if `n_channels == 1`, or 2D array of shape
        `(n_channels, n_samples)` if `n_channels > 1`.
    """
    if n_samples <= 0:
        raise ValueError(f"n_samples must be strictly positive, got {n_samples}")
    if n_channels <= 0:
        raise ValueError(f"n_channels must be strictly positive, got {n_channels}")
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive, got {fs}")
    if sigma_innov <= 0 or not np.isfinite(sigma_innov):
        raise ValueError(f"sigma_innov must be strictly positive, got {sigma_innov}")

    if tau_s is not None and poles is not None:
        raise ValueError("Cannot specify both tau_s and poles; choose one.")

    if poles is not None:
        ar_coeffs = np.asarray(poles, dtype=float).ravel()
        if len(ar_coeffs) == 0:
            raise ValueError("poles sequence cannot be empty")
        # Check stability: roots of 1 - sum(phi_k * z^-k) must lie inside unit circle
        poly = np.concatenate([[1.0], -ar_coeffs])
        roots = np.roots(poly)
        if np.any(np.abs(roots) >= 1.0):
            raise ValueError(f"AR process is non-stationary: root magnitudes {np.abs(roots)}")
    elif tau_s is not None:
        tau_s = float(tau_s)
        if tau_s <= 0 or not np.isfinite(tau_s):
            raise ValueError(f"tau_s must be strictly positive, got {tau_s}")
        phi = float(np.exp(-1.0 / (fs * tau_s)))
        ar_coeffs = np.array([phi])
    else:
        # Default: AR(1) with 50 ms time constant
        phi = float(np.exp(-1.0 / (fs * 0.05)))
        ar_coeffs = np.array([phi])

    gen = np.random.default_rng(rng)
    burn_in = max(200, len(ar_coeffs) * 20)
    total_samples = n_samples + burn_in

    white = gen.normal(loc=0.0, scale=sigma_innov, size=(n_channels, total_samples))
    a_poly = np.concatenate([[1.0], -ar_coeffs])
    b_poly = np.array([1.0])

    # Filter across samples
    filtered = signal.lfilter(b_poly, a_poly, white, axis=-1)
    out = filtered[:, burn_in:]

    if n_channels == 1:
        return out[0]
    return out


def synth_periodic_response(
    n_trials: int,
    n_samples: int,
    fs: float,
    *,
    freq_hz: float = 20.0,
    n_channels: int = 1,
    amplitude: float = 1.0,
    noise_std: float = 0.5,
    phase_jitter_rad: float = 0.0,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> np.ndarray:
    """Generate multi-trial shared periodic responses with controlled trial-to-trial jitter.

    Constructs common oscillatory drive across trials for evaluating null hypotheses and
    verifying false-positive rate control across conditions.

    Args:
        n_trials: Number of trials.
        n_samples: Number of samples per trial.
        fs: Sampling rate in Hz.
        freq_hz: Frequency of the shared periodic oscillation (Hz).
        n_channels: Number of channels per trial (default 1).
        amplitude: Amplitude of the oscillation.
        noise_std: Standard deviation of additive Gaussian noise.
        phase_jitter_rad: Standard deviation of trial-to-trial phase jitter in radians.
        rng: Optional NumPy Generator or integer seed.

    Returns:
        Array of shape `(n_trials, n_samples)` if `n_channels == 1`, or
        `(n_trials, n_channels, n_samples)` if `n_channels > 1`.
    """
    if n_trials <= 0:
        raise ValueError(f"n_trials must be strictly positive, got {n_trials}")
    if n_samples <= 0:
        raise ValueError(f"n_samples must be strictly positive, got {n_samples}")
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive, got {fs}")
    if freq_hz <= 0 or freq_hz >= fs / 2.0:
        raise ValueError(f"freq_hz must be in (0, Nyquist); got {freq_hz}")

    gen = np.random.default_rng(rng)
    t = np.arange(n_samples, dtype=float) / float(fs)

    jitters = (
        gen.normal(0.0, phase_jitter_rad, size=n_trials)
        if phase_jitter_rad > 0
        else np.zeros(n_trials)
    )

    if n_channels == 1:
        out = np.empty((n_trials, n_samples), dtype=float)
        for i in range(n_trials):
            osc = amplitude * np.cos(2.0 * np.pi * freq_hz * t + jitters[i])
            noise = gen.normal(0.0, noise_std, size=n_samples) if noise_std > 0 else 0.0
            out[i] = osc + noise
        return out
    else:
        out = np.empty((n_trials, n_channels, n_samples), dtype=float)
        for i in range(n_trials):
            osc = amplitude * np.cos(2.0 * np.pi * freq_hz * t + jitters[i])
            noise = (
                gen.normal(0.0, noise_std, size=(n_channels, n_samples))
                if noise_std > 0
                else 0.0
            )
            out[i] = osc[np.newaxis, :] + noise
        return out


def synth_correlation_blocks(
    block_sizes: Sequence[int],
    *,
    within_corr: float = 0.8,
    between_corr: float = 0.0,
    n_samples: int = 1000,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate multi-channel signals with known block-diagonal correlation structure.

    Designed for testing spatial boundary detection, xFLIP contact partitioning,
    and modular community clustering algorithms.

    Args:
        block_sizes: Sequence of positive integers indicating channel counts per contiguous block.
        within_corr: Pearson correlation coefficient between contacts within the same block.
        between_corr: Pearson correlation coefficient between contacts in different blocks.
        n_samples: Number of temporal observations per channel.
        rng: Optional NumPy Generator or integer seed.

    Returns:
        `(data, true_labels, true_corr)`:
        - `data`: `(n_channels, n_samples)` array of synthesized correlated time series.
        - `true_labels`: `(n_channels,)` integer array of block membership (0, 1, ...).
        - `true_corr`: `(n_channels, n_channels)` theoretical correlation matrix.
    """
    sizes = [int(s) for s in block_sizes]
    if len(sizes) == 0 or any(s <= 0 for s in sizes):
        raise ValueError(f"block_sizes must be non-empty positive integers, got {block_sizes}")
    if n_samples <= 1:
        raise ValueError(f"n_samples must be > 1, got {n_samples}")
    if not (-1.0 <= within_corr <= 1.0) or not (-1.0 <= between_corr <= 1.0):
        raise ValueError("Correlations must be in [-1, 1]")

    n_channels = sum(sizes)
    true_corr = np.full((n_channels, n_channels), between_corr, dtype=float)
    np.fill_diagonal(true_corr, 1.0)

    true_labels = np.empty(n_channels, dtype=int)
    offset = 0
    for block_id, sz in enumerate(sizes):
        idx = slice(offset, offset + sz)
        true_corr[idx, idx] = within_corr
        np.fill_diagonal(true_corr[idx, idx], 1.0)
        true_labels[idx] = block_id
        offset += sz

    # Verify positive semi-definiteness via eigenvalue thresholding
    eigenvals, eigenvecs = np.linalg.eigh(true_corr)
    if np.any(eigenvals < 0):
        # Clip negative eigenvalues to ensure numerical validity
        eigenvals = np.maximum(eigenvals, 1e-10)
        true_corr = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
        # Rescale diagonal to 1.0
        d_inv = 1.0 / np.sqrt(np.diag(true_corr))
        true_corr = true_corr * d_inv[:, None] * d_inv[None, :]

    # Cholesky factor
    L = np.linalg.cholesky(true_corr)
    gen = np.random.default_rng(rng)
    z = gen.normal(0.0, 1.0, size=(n_channels, n_samples))
    data = L @ z

    return data, true_labels, true_corr


def synth_phase_gradient(
    n_channels: int,
    n_samples: int,
    fs: float,
    *,
    f0: float = 25.0,
    delay_per_channel_s: float = 0.002,
    noise_std: float = 0.2,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> np.ndarray:
    """Generate linear array signals with a known traveling-wave phase gradient.

    Yields a constant spatial delay ``tau_c = c * delay_per_channel_s`` across ordered contacts,
    producing an analytical phase slope ``d(Delta phi) / df = -2 * pi * Delta tau`` for calibrating
    zFLIP and Phase Slope Index (PSI) directionality.

    Args:
        n_channels: Number of ordered channels along the array.
        n_samples: Number of time samples.
        fs: Sampling frequency in Hz.
        f0: Center oscillation frequency in Hz.
        delay_per_channel_s: Latency increment per contact in seconds.
        noise_std: Standard deviation of additive white noise.
        rng: Optional NumPy Generator or integer seed.

    Returns:
        Array of shape `(n_channels, n_samples)`.
    """
    if n_channels <= 0:
        raise ValueError(f"n_channels must be strictly positive, got {n_channels}")
    if n_samples <= 0:
        raise ValueError(f"n_samples must be strictly positive, got {n_samples}")
    if fs <= 0 or not np.isfinite(fs):
        raise ValueError(f"fs must be strictly positive, got {fs}")

    gen = np.random.default_rng(rng)
    t = np.arange(n_samples, dtype=float) / float(fs)
    data = np.empty((n_channels, n_samples), dtype=float)

    for c in range(n_channels):
        tau = c * float(delay_per_channel_s)
        sig = np.sin(2.0 * np.pi * f0 * (t - tau))
        noise = gen.normal(0.0, noise_std, size=n_samples) if noise_std > 0 else 0.0
        data[c] = sig + noise

    return data


def synth_unequal_groups(
    n_trials_1: int,
    n_trials_2: int,
    n_features: int,
    *,
    effect_size: float = 0.0,
    noise_std: float = 1.0,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate two sample groups with unequal sizes for statistical comparison tests.

    Group 1 has mean 0; Group 2 has mean ``effect_size * noise_std``.

    Args:
        n_trials_1: Sample count for group 1 (must be >= 1).
        n_trials_2: Sample count for group 2 (must be >= 1).
        n_features: Number of features / observations per trial.
        effect_size: Cohen's d style mean displacement in units of noise_std.
        noise_std: Standard deviation of observation noise.
        rng: Optional NumPy Generator or integer seed.

    Returns:
        `(group1, group2)` with shapes `(n_trials_1, n_features)` and `(n_trials_2, n_features)`.
    """
    if n_trials_1 <= 0 or n_trials_2 <= 0:
        raise ValueError("Sample sizes must be strictly positive")
    if n_features <= 0:
        raise ValueError("n_features must be strictly positive")

    gen = np.random.default_rng(rng)
    g1 = gen.normal(0.0, noise_std, size=(n_trials_1, n_features))
    g2 = gen.normal(float(effect_size) * noise_std, noise_std, size=(n_trials_2, n_features))
    return g1, g2


def synth_laminar_motif(
    n_channels: int = 24,
    n_samples: int = 5000,
    fs: float = 1000.0,
    *,
    c_crossover: float = 12.0,
    orientation: str = "superficial_to_deep",
    pitch_um: float = 50.0,
    gamma_freq: float = 75.0,
    beta_freq: float = 18.0,
    snr: float = 4.0,
    bad_channels: Optional[Sequence[int]] = None,
    rng: Optional[Union[np.random.Generator, int]] = None,
) -> SynthLaminarReceipt:
    """Generate a multi-channel LFP recording with an analytically known spectrolaminar motif.

    Constructs superficial gamma dominance, deep alpha/beta dominance, an exact zero-crossing
    crossover contact, physical linear geometry, and optional damaged/disconnected contacts.

    Args:
        n_channels: Number of contacts along the shaft (default 24).
        n_samples: Number of time samples (default 5000).
        fs: Sampling rate in Hz (default 1000.0).
        c_crossover: True continuous crossover contact coordinate (default 12.0).
        orientation: Probe orientation ('superficial_to_deep' or 'deep_to_superficial').
        pitch_um: Contact spacing in micrometers (default 50.0 um).
        gamma_freq: Frequency of the supragranular gamma peak (Hz).
        beta_freq: Frequency of the infragranular alpha/beta peak (Hz).
        snr: Signal-to-noise ratio multiplier for laminar spectral peaks over background.
        bad_channels: Optional sequence of channel indices to render dead/disconnected.
        rng: Optional NumPy Generator or integer seed.

    Returns:
        SynthLaminarReceipt containing LFP array, geometry, and analytical ground-truth.
    """
    if n_channels < 4:
        raise ValueError(f"n_channels must be at least 4; got {n_channels}")
    if n_samples <= 0 or fs <= 0:
        raise ValueError("n_samples and fs must be positive")
    if not (0 <= c_crossover <= n_channels - 1):
        raise ValueError(f"c_crossover ({c_crossover}) must lie within [0, {n_channels - 1}]")
    if orientation not in ("superficial_to_deep", "deep_to_superficial"):
        raise ValueError(f"Unknown orientation '{orientation}'")

    gen = np.random.default_rng(rng)
    t = np.arange(n_samples, dtype=float) / float(fs)

    # 1. Background 1/f-like noise across all contacts
    lfp = synth_ar_noise(n_samples, n_channels=n_channels, tau_s=0.03, fs=fs, sigma_innov=1.0, rng=gen)

    # 2. Spatially graded laminar oscillations
    g_low = max(2.0, gamma_freq - 15.0)
    g_high = min(fs / 2.0 - 5.0, gamma_freq + 15.0)
    b_low = max(2.0, beta_freq - 5.0)
    b_high = min(fs / 2.0 - 5.0, beta_freq + 5.0)

    sos_gamma = signal.butter(4, [g_low, g_high], btype="bandpass", fs=fs, output="sos")
    sos_beta = signal.butter(4, [b_low, b_high], btype="bandpass", fs=fs, output="sos")

    src_gamma = signal.sosfiltfilt(sos_gamma, gen.normal(0.0, 1.0, size=(n_channels, n_samples)), axis=-1)
    src_beta = signal.sosfiltfilt(sos_beta, gen.normal(0.0, 1.0, size=(n_channels, n_samples)), axis=-1)

    for ch in range(n_channels):
        if orientation == "superficial_to_deep":
            if ch <= c_crossover:
                gw = 1.0 - (ch / max(c_crossover, 1.0)) * 0.5
                bw = (ch / max(c_crossover, 1.0)) * 0.5
            else:
                gw = 0.5 * (1.0 - (ch - c_crossover) / max(n_channels - 1 - c_crossover, 1.0))
                bw = 0.5 + 0.5 * (ch - c_crossover) / max(n_channels - 1 - c_crossover, 1.0)
        else:
            if ch <= c_crossover:
                bw = 1.0 - (ch / max(c_crossover, 1.0)) * 0.5
                gw = (ch / max(c_crossover, 1.0)) * 0.5
            else:
                bw = 0.5 * (1.0 - (ch - c_crossover) / max(n_channels - 1 - c_crossover, 1.0))
                gw = 0.5 + 0.5 * (ch - c_crossover) / max(n_channels - 1 - c_crossover, 1.0)

        lfp[ch] += snr * (gw * src_gamma[ch] + bw * src_beta[ch])

    # 3. Bad channels injection
    bad_mask = np.zeros(n_channels, dtype=bool)
    if bad_channels is not None:
        for b_ch in bad_channels:
            if 0 <= b_ch < n_channels:
                bad_mask[b_ch] = True
                lfp[b_ch] = 0.0  # Flat dead channel

    # 4. Probe geometry
    contacts = np.arange(n_channels, dtype=float)
    z_coords = contacts * float(pitch_um)
    df_geom = pd.DataFrame({
        "x": np.zeros(n_channels),
        "y": np.zeros(n_channels),
        "z": z_coords,
        "channel_id": [f"ch_{i}" for i in range(n_channels)],
    })
    geom = probe_geometry(df_geom, units="um", nominal_pitch=float(pitch_um))

    true_depth_um = float(c_crossover * pitch_um)

    return SynthLaminarReceipt(
        lfp=lfp,
        fs=float(fs),
        crossover_contact=float(c_crossover),
        crossover_depth_um=true_depth_um,
        orientation=orientation,
        probe_geometry=geom,
        bad_channel_mask=bad_mask,
        pitch_um=float(pitch_um),
        gamma_freq=float(gamma_freq),
        beta_freq=float(beta_freq),
    )


def build_canonical_tutorial_nwb(
    output_path: Optional[Union[str, Path]] = None,
    *,
    n_channels: int = 24,
    pitch_um: float = 50.0,
    fs: float = 1000.0,
    duration_s: float = 10.0,
    n_trials: int = 20,
    seed: int = 42,
) -> Tuple[Any, Dict[str, Any]]:
    """Build a comprehensive, self-contained synthetic NWB file for executable tutorials.

    Assembles:
    - 24-contact linear probe geometry with laminar coordinates
    - Multi-channel LFP exhibiting an analytically known spectrolaminar crossover
    - Unit spike trains with known PSTH latency and causal exponential onset
    - Trial interval table with condition codes and behavioral markers

    Args:
        output_path: Optional file path to write the synthetic NWB file to disk.
        n_channels: Contact count for the probe shaft.
        pitch_um: Inter-contact spacing in micrometers.
        fs: Sampling frequency in Hz.
        duration_s: Total recording duration in seconds.
        n_trials: Number of task trials.
        seed: Random seed for analytical reproducibility.

    Returns:
        `(nwbfile, ground_truth)`: The PyNWB NWBFile instance and ground-truth parameters dictionary.
    """
    import pynwb
    from datetime import datetime
    from dateutil.tz import tzutc

    rng = np.random.default_rng(seed)
    n_samples = int(duration_s * fs)

    # 1. Base NWB file
    nwb = pynwb.NWBFile(
        session_description="Canonical synthetic tutorial recording",
        identifier=f"synth-tutorial-{seed}",
        session_start_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=tzutc()),
    )

    # 2. Electrodes and Device
    device = nwb.create_device(name="tutorial_probe_device")
    eg = nwb.create_electrode_group(
        name="linear_shank",
        description="24-channel linear probe",
        location="cortex",
        device=device,
    )
    for ch in range(n_channels):
        nwb.add_electrode(
            x=0.0,
            y=0.0,
            z=float(ch * pitch_um),
            imp=1.0,
            location="cortex",
            filtering="none",
            group=eg,
        )

    # 3. Laminar LFP
    crossover_true = 10.5
    laminar_res = synth_laminar_motif(
        n_channels=n_channels,
        n_samples=n_samples,
        fs=fs,
        c_crossover=crossover_true,
        pitch_um=pitch_um,
        rng=rng,
    )

    # Add LFP electrical series
    region = nwb.create_electrode_table_region(
        region=list(range(n_channels)),
        description="All probe electrodes",
    )
    es = pynwb.ecephys.ElectricalSeries(
        name="lfp",
        data=laminar_res.lfp.T.astype(np.float32),  # (time, channels)
        electrodes=region,
        rate=float(fs),
        starting_time=0.0,
    )
    ecephys_module = nwb.create_processing_module(name="ecephys", description="LFP processing")
    lfp_container = pynwb.ecephys.LFP(name="LFP")
    lfp_container.add_electrical_series(es)
    ecephys_module.add(lfp_container)

    # 4. Trials table
    trial_duration = duration_s / (n_trials + 1)
    onsets = np.array([i * trial_duration + 0.2 for i in range(n_trials)])
    trials = pynwb.epoch.TimeIntervals(name="trials", description="Task trials")
    trials.add_column(name="condition", description="Condition label")
    trials.add_column(name="condition_code", description="Numeric condition code")
    trials.add_column(name="correct", description="Correctness flag")

    for i, onset in enumerate(onsets):
        cond = "A" if (i % 2 == 0) else "B"
        trials.add_row(
            start_time=float(onset),
            stop_time=float(onset + trial_duration * 0.8),
            condition=cond,
            condition_code=float(1 if cond == "A" else 2),
            correct=1.0,
        )
    nwb.add_time_intervals(trials)

    # 5. Units (Spikes) with known PSTH response
    unit0_spikes = []
    unit1_spikes = []

    # Baseline Poisson rate 5 Hz
    t_curr = 0.0
    while t_curr < duration_s:
        t_curr += rng.exponential(1.0 / 5.0)
        if t_curr < duration_s:
            unit1_spikes.append(t_curr)

    # Unit 0 fires at baseline 2 Hz plus burst at onsets for condition A
    t_curr = 0.0
    while t_curr < duration_s:
        t_curr += rng.exponential(1.0 / 2.0)
        if t_curr < duration_s:
            unit0_spikes.append(t_curr)

    for i, onset in enumerate(onsets):
        if i % 2 == 0:  # Condition A
            # Burst around onset + 0.050 s
            for _ in range(rng.integers(3, 8)):
                unit0_spikes.append(float(onset + 0.050 + rng.normal(0.0, 0.005)))

    unit0_spikes.sort()
    unit1_spikes.sort()

    nwb.add_unit(spike_times=np.array(unit0_spikes, dtype=float), electrodes=[10])
    nwb.add_unit(spike_times=np.array(unit1_spikes, dtype=float), electrodes=[18])

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with pynwb.NWBHDF5IO(str(p), "w") as io:
            io.write(nwb)

    ground_truth = {
        "n_channels": n_channels,
        "pitch_um": pitch_um,
        "fs": fs,
        "duration_s": duration_s,
        "crossover_contact": crossover_true,
        "crossover_depth_um": crossover_true * pitch_um,
        "n_trials": n_trials,
        "trial_onsets": onsets,
        "unit0_latency_s": 0.050,
    }

    return nwb, ground_truth
