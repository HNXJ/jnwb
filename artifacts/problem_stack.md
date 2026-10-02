# Problem stack

Problems found and not yet triaged. Triage creates work in `artifacts/todo_stack.md`.

## The rule

A release requires this file to hold no problem row (`AGENTS.md` section 11, ruled 2026-09-23).
A problem leaves in one of three ways: it is repaired, or it is shown false, and its row is
deleted with the evidence in the commit message; or it moves into the todo stack as work, marked
`required-<cycle>` when it meets the blocker predicate of section 11 and `deferred-<next>`
otherwise, where `<cycle>` is the version being released and `<next>` the one after it. Git
holds every row that has left.

## Open

| ID | Problem | Found by |
|---|---|---|
| P-354 | `vflip_from_lfp` defaults `nperseg` to `min(n_times, int(fs))` and checks only `>= 1`. `vflip_from_lfp(rng.standard_normal((16, 100)), fs=0.5)` raises `nperseg must be in range [1, 100], got 0` (`laminar.py:864`), naming an argument the caller left unset; `fs=1.0` passes with `nperseg=1` and fails downstream with `freqs must have at least 4 frequency bins, got 1` (`laminar.py:406`). `compute_psd` had the same default and was repaired in 91637f62. | Sweep by jnwb-agy-dev at e2ad0b9c; reproduced at 8821d0c2 |
| P-355 | `fit_exponential_onset` documents that `None` on either side of `t0_bounds_ms` defaults to the trace's own range (`onset_fitting.py:118`), but the unset argument resolves to a lower bound of 0.0. `fit_exponential_onset(np.linspace(-200, -10, 50), np.ones(50))` raises `t0 bounds are empty: [0.0, -10.0]` (`onset_fitting.py:165`), so a window that ends before 0 ms cannot be fitted with the defaults. | Sweep by jnwb-agy-dev at e2ad0b9c; reproduced at 8821d0c2 |
| P-356 | A 1-sample trace returns zero power instead of a refusal. `band_power(np.array([5.0]), fs=1000.0, freq_range=(0.0, 10.0), normalize=False)` returns `0.0`; `harmonic_analysis` on the same input returns `spectral_profile` `array([0.])` with `fundamental_freq` NaN. `compute_psd` refuses this case because a 0.0 PSD reads as a measured absence of power. | Sweep by jnwb-agy-dev at e2ad0b9c; reproduced at 8821d0c2 |
| P-357 | `synth_laminar_motif(fs=100.0, rng=0)` raises scipy's `Wn[0] must be less than Wn[1]` from the gamma band-pass design: the band derived from `fs` and the default `gamma_freq=75.0` is empty and `fs` is not checked against it. `fs=140.0` and `fs=200.0` return a receipt, so the reported `fs < 150` threshold did not reproduce; the failing range is unmeasured. | Sweep by jnwb-agy-dev at e2ad0b9c; reproduced at 8821d0c2 |
| P-358 | `cross_modal_comparison` does not validate `bin_ms`. `cross_modal_comparison(x, y, bin_ms=0, n_permutations=10, rng=0)` on two 200-sample series raises `ZeroDivisionError: division by zero` (`statistics.py:1618`). | Sweep by jnwb-agy-dev at e2ad0b9c; reproduced at 8821d0c2 |
