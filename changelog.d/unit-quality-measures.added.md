- Unit quality measures in `jnwb.unit_quality`, each for one sorted unit:
  `waveform_features(waveform, fs)` gives the peak channel, amplitude, trough-to-peak duration
  (ms), peak-trough ratio and polarity of a mean waveform `(n_channels, n_samples)`;
  `waveform_snr(spike_waveforms)` the amplitude over twice the residual standard deviation;
  `presence_ratio(spike_times, blocks)` the fraction of caller-given blocks holding a spike;
  and `isi_cv(spike_times)` the coefficient of variation of the inter-spike intervals, each
  citing its published definition in `docs/references.md`. `waveform_flatness` and
  `spatial_derivative_sharpness` have no published source and take a required `threshold`.
  Undefined input is NaN or raises `ValueError` naming the reason, never 0.
