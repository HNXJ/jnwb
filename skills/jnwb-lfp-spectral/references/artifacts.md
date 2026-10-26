### Artifacts
- `jnwb.channel_correlation_matrix(data_ch_by_time)` & `jnwb.bad_channels_from_correlation(corr, z_thresh=5.0)`: Detect disconnected or excessively noisy probe channels.
- `jnwb.bad_trials_single_channel(trial_waveforms, corr_z_thresh=5.0, amp_z_thresh=5.0)`: Flags trials of one good channel, shaped `(n_trials, n_times)`, by correlation to the trial mean and by amplitude.
- `jnwb.trial_correlation_matrix(trial_waveforms)`: The `(n_trials, n_trials)` correlation matrix of one channel's trials, which `bad_trials_single_channel` reads.
- `jnwb.consensus_bad_trials(per_channel_flags, min_frac_channels=0.5)`: Reduces `(n_good_channels, n_trials)` per-channel flags to a trial verdict; a trial is excluded only when at least `min_frac_channels` of channels flag it, so one bad channel cannot delete the session.
- `jnwb.repair_lfp_trials(segments, times_ms, z_thresh=6.0)` → `(repaired, frac_flagged, info)`: Cross-channel synchrony detection ($z > 6.0$) and cross-trial median substitution. `frac_flagged` is the fraction of (trial, time) cells substituted (invariant 4).
- `jnwb.detect_band_outliers(band_trace, z_thresh=6.0, sided="upper")`: Flags `(trial, time)` cells departing from the cross-trial trend.
- `jnwb.repair_band_artifacts(power, freqs, band_ranges=None, z_thresh=6.0, sided="upper")` → `(repaired, frac_flagged_by_band)`: TFR-domain outlier detection per band, repaired by cross-trial median substitution at the flagged (trial, time) cells.
