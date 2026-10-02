- `jnwb.vflip_from_lfp` accepts `nperseg` from 6, the shortest segment that gives the 4
  frequency bins `vflip` needs, to `n_times`, and says so when the value came from the
  default. At `fs` below 1 Hz the default was 0 and the error named an argument the caller
  had not passed; a segment of 1 to 5 samples was refused later by a message about `freqs`.
- `jnwb.fit_exponential_onset` called without `t0_bounds_ms` on a trace that ends at or
  before 0 ms names the default lower bound of 0 ms in its error and how to override it.
  The docstring now states that default. Fitted values are unchanged.
- `jnwb.band_power` and `jnwb.harmonic_analysis` raise `ValueError` for a 1-sample trace or
  baseline. They returned a power of 0.0, which reads as a measured absence of power;
  `compute_psd` already refused this input.
- `jnwb.testing.synth_laminar_motif` raises `ValueError` naming `fs` when `fs` leaves the
  gamma or beta peak no pass band (130 Hz or less under the default `gamma_freq`), in place
  of an error from the SciPy filter design.
- `jnwb.cross_modal_comparison` raises `ValueError` for a `bin_ms` that is not positive and
  finite. `bin_ms=0` raised `ZeroDivisionError`.
