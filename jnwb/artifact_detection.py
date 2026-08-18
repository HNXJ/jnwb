r"""
jnwb.artifact_detection -- bad-channel and bad-trial DETECTION (exclusion), for raw wideband LFP.

Distinct from jnwb.artifact_repair (interpolation/substitution of flagged samples within a
kept trial). This module decides what to DROP entirely: whole channels, whole trials.

Method (Hamm, 2026-08-17):

Bad channels: correlate every channel's raw trace against every other channel
(channel x channel Pearson correlation matrix, pooled across all trials/time). A channel whose
sensor contact is damaged or detached is uncorrelated with the rest of the probe -- its own
noise, not shared local field -- so its row of the correlation matrix separates out as a low
outlier relative to every other (good) channel's row. Per-channel summary statistic = median
off-diagonal correlation; flagged via a robust (MAD-based) z-score against the OTHER channels'
summaries, not a fixed correlation cutoff (channel-to-channel correlation baseline varies by
session/probe/reference scheme, so a fixed threshold does not transfer across sessions).

Bad trials: for a single GOOD channel, correlate every trial's waveform against every other
trial's waveform (trial x trial Pearson correlation matrix). A trial contaminated by a
transient artifact (movement, chewing, cable jerk) looks different from the bulk of trials for
that channel, so it separates out as a low-correlation outlier the same way a bad channel does
-- plus its own max |amplitude| is an outlier high. Per spec: "artifacts appear in all good
channels always, if they exist" -- a genuine artifact is a shared physical event, not a
single-channel quirk, so a trial is only called bad by CONSENSUS across multiple good channels'
independent flags, not from one channel's flag alone (a single flagged channel more likely means
that channel is itself imperfectly screened, not that the trial is bad).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np

MAD_SCALE = 1.4826  # normal-consistent scaling for the median absolute deviation


def _robust_z(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    center = np.median(x)
    mad = np.median(np.abs(x - center)) * MAD_SCALE
    if mad < 1e-12:
        return np.zeros_like(x)
    return (x - center) / mad


def channel_correlation_matrix(data_ch_by_time: np.ndarray) -> np.ndarray:
    """data_ch_by_time: (n_channels, n_samples). Returns (n_channels, n_channels) Pearson corr."""
    return np.corrcoef(np.asarray(data_ch_by_time, dtype=float))


def bad_channels_from_correlation(corr: np.ndarray, z_thresh: float = 5.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """corr: (n_ch, n_ch). Returns (bad_mask, summary_per_channel, z_per_channel).

    summary = median off-diagonal correlation for that channel's row (how well it agrees with
    the rest of the probe). bad = summary is a robust-z low outlier vs the OTHER channels'
    summaries (self-referential: a session with genuinely no bad channels should flag ~0)."""
    n = corr.shape[0]
    off_diag_mask = ~np.eye(n, dtype=bool)
    summary = np.array([np.median(corr[i][off_diag_mask[i]]) for i in range(n)])
    z = _robust_z(summary)
    bad = z < -z_thresh
    return bad, summary, z


def trial_correlation_matrix(trial_waveforms: np.ndarray) -> np.ndarray:
    """trial_waveforms: (n_trials, n_times), single channel. Returns (n_trials, n_trials) corr."""
    return np.corrcoef(np.asarray(trial_waveforms, dtype=float))


def bad_trials_single_channel(
    trial_waveforms: np.ndarray, corr_z_thresh: float = 5.0, amp_z_thresh: float = 5.0
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """trial_waveforms: (n_trials, n_times), single GOOD channel.

    Returns (flag_per_trial, corr_summary_per_trial, amp_per_trial). A trial is flagged if its
    median correlation to all other trials on this channel is a low robust-z outlier, OR its own
    max |amplitude| is a high robust-z outlier (either is sufficient on a single channel; cross-
    channel consensus below is what actually decides exclusion)."""
    trial_waveforms = np.asarray(trial_waveforms, dtype=float)
    n = trial_waveforms.shape[0]
    corr = trial_correlation_matrix(trial_waveforms)
    off_diag_mask = ~np.eye(n, dtype=bool)
    corr_summary = np.array([np.median(corr[i][off_diag_mask[i]]) for i in range(n)])
    corr_z = _robust_z(corr_summary)
    max_amp = np.max(np.abs(trial_waveforms), axis=1)
    amp_z = _robust_z(max_amp)
    flag = (corr_z < -corr_z_thresh) | (amp_z > amp_z_thresh)
    return flag, corr_z, amp_z


def consensus_bad_trials(per_channel_flags: np.ndarray, min_frac_channels: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
    """per_channel_flags: (n_good_channels, n_trials) bool. A trial is excluded only if flagged
    on at least `min_frac_channels` of the good channels independently -- the cross-channel-
    consensus requirement (real artifacts are shared events, not one channel's quirk).

    Returns (consensus_bad_mask, frac_channels_flagged_per_trial)."""
    per_channel_flags = np.asarray(per_channel_flags, dtype=bool)
    if per_channel_flags.shape[0] == 0:
        n_trials = per_channel_flags.shape[1] if per_channel_flags.ndim == 2 else 0
        return np.zeros(n_trials, dtype=bool), np.zeros(n_trials)
    frac = per_channel_flags.mean(axis=0)
    return frac >= min_frac_channels, frac
