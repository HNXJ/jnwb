- Unit quality measures in `jnwb.unit_quality`, each for one sorted unit:
  `waveform_features(waveform, fs)` gives the peak channel, amplitude, duration (ms, from the
  larger extremum to the opposite one after it), peak-trough ratio and polarity of a mean waveform `(n_channels, n_samples)`;
  `waveform_snr(spike_waveforms)` the amplitude over twice the residual standard deviation;
  `presence_ratio(spike_times, blocks)` the fraction of caller-given blocks holding a spike;
  `isi_cv(spike_times)` the coefficient of variation of the inter-spike intervals, with the
  unbiased (`ddof=1`) standard deviation; and
  `refractory_contamination(spike_times, *, duration_s, refractory_ms, censored_ms)` the
  fraction of contaminating spikes by the estimate of Hill et al. (2011), the refractory and
  censored periods required. Each cites its published definition in `docs/references.md`. `waveform_flatness` and
  `spatial_derivative_sharpness` have no published source and take a required `threshold`.
  Undefined input is NaN or raises `ValueError` naming the reason, never 0.
