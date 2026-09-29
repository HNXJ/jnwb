---
name: jnwb-connectivity
description: Directed connectivity, bivariate Granger causality, phase slope index
  (PSI), transfer entropy, and graph measures.
---

# `jnwb-connectivity` — Directed Connectivity & Functional Coupling

## 1. Trigger
Directional coupling, lag asymmetry, Granger causality, phase slope index or transfer entropy across regions or channels.

## 2. Routing

### Directed measures
- `jnwb.granger(X, Y, order="auto", n_surrogates=0, rng=0)`: Time-domain bivariate Granger causality with surrogate significance (scheme in invariant 3).
- `jnwb.granger_spectral(X, Y, fs, order="auto", n_freqs=256, bands=None)`: Frequency-resolved spectral Granger causality.
- `jnwb.phase_slope_index(X, Y, fs, bands, nperseg=None, jackknife=True, n_surrogates=0)`: Phase slope index (PSI), the frequency-dependent driver/receiver lag. `p_net` (equal to `p_x_to_y` and `p_y_to_x`) is the jackknife t test of a lead and is None with `jackknife=False`; `diagnostics['p_coupling_surrogate']` is the surrogate p, which tests coupling of any lag, zero lag included, and never a lead. Under a zero-lag common source the lead p rejects at 0.06 to 0.08 for a nominal 0.05. Set `nperseg` so the record holds tens of segments. A band holding fewer than two frequency bins has no slope: its `per_band` value is NaN and `diagnostics['ok_for_interpretation']` is False. When no band has a slope, `net`, `x_to_y` and `y_to_x` are NaN; when only some do, `net` sums the bands that have one, so read `per_band` before `net`.
- `jnwb.transfer_entropy(X, Y, k=1, l=1, estimator="quantile", n_surrogates=...)`: Transfer entropy in bits. `estimator` is `"quantile"`, `"uniform"` or `"discrete"` (integer spike counts); `"symbolic"` raises `ValueError`, because its surrogate null is not calibrated under zero-lag mixing and a common source with no directed coupling tests significant in both directions. The surrogate p compares plug-in values; `bias_correction` changes only the reported estimate. `"quantile"` is calibrated under zero-lag mixing only for a white common source (0.025 to 0.06 at 4 bins, `k = l = 1`, n = 500 to 8000); a coloured common source tests significant, as in Granger, and the p is conservative at large state spaces (8 bins, or `k = l = 2`).
- `jnwb.directed_connectivity(X, Y, method="granger")`: One directed measure between two signals, returning `DirectedResult`; method-specific kwargs are forwarded. `method` names a directed estimator; an unsigned coupling measure such as `"wpli"` raises `ValueError`.
- `jnwb.directed_network(signals, method="granger", labels=None, fdr=True, n_jobs=1)`: All-pairs directed coupling for a dict or array of channel signals.
- `jnwb.network_topology(adjacency_matrix, threshold=0.3)`: Graph metrics on a thresholded adjacency matrix. A complex matrix raises `TypeError`; pass `np.abs(matrix)` to threshold the magnitude.
- `jnwb.granger_causality(signal1, signal2, order=5, device="cpu", ridge=0.0, criterion="aic")`: Raw bivariate Granger values in a dict (`F_1_to_2`, `F_2_to_1`), with no surrogate testing. Deprecated: every call emits `DeprecationWarning`; use `granger`, which carries the surrogate test and returns a `DirectedResult`. A fixed `order` is an integer >= 1 in all three Granger calls; `0`, a fraction or a bool raises. Directional language is licensed by prediction improvement, not by causation.

### Spike and cross-modal association
- `jnwb.spike_mutual_information(spike_times1, spike_times2, time_window_s=None, bin_size_ms=10.0, estimator="binary_occupancy")`, `jnwb.binary_occupancy_mutual_information(spike_times1, spike_times2, time_window_s=None, bin_size_ms=10.0)` and `jnwb.spike_count_mutual_information(spike_times1, spike_times2, time_window_s=None, bin_size_ms=10.0)`: Mutual information between two spike trains, in **bits** ($\log_2$). MI is symmetric: it carries no direction however the arguments are ordered. `time_window_s` is required although the signature allows `None`: omitted, all three raise `ValueError`, as they do for a span that is not whole `bin_size_ms` bins.
- `jnwb.cross_modal_comparison(tfr_data, spike_data, lag_range_ms=(-500, 500), bin_ms=None, n_permutations=1000, rng=None)`: Correlation between a TFR-derived series and a spike-count series, both reduced to 1-D as `(n_times, n_trials)`. **`bin_ms` selects which of two estimators runs, and the default is not the lag search.** The reduced series carry no bin width, so `lag_range_ms` cannot become a sample shift without one. With `bin_ms=None` the result is a single zero-lag correlation: `lag_range_ms`, `n_permutations` and `rng` are accepted and unused, `lag_ms` is `0.0`, and there is no `lag_corrected_pvalue` key. Pass `bin_ms` (the bin width of the reduced series, in ms) for the lag sweep: `lag_ms` is then negative when the LFP leads spikes, and you read `lag_corrected_pvalue`, not the parametric p, which pays nothing for the lag search; `surrogate_seed_entropy` is the seed of its null, and passing it back as `rng` reproduces it. `interpretation` names which of the two ran. It correlates two modalities without pooling them into one feature space, which is what the no-pooling rule forbids; report it as a cross-modal association at a lag, never as one modality driving the other.

## 3. Invariants & Safeguards
1. **Epistemic language**: Granger causality, PSI and transfer entropy measure **temporal-lag asymmetry (predictive directionality)** under an observational model. Never use causal verbs ("region A drives region B causally") for observational time-series metrics.
2. **Stationarity**: time-domain Granger requires wide-sense stationary inputs; demean and detrend before fitting.
3. **Surrogate nulls**: significance comes from surrogates that destroy cross-signal alignment while preserving each signal's autocorrelation. `granger`, `granger_spectral`, `phase_slope_index` and `transfer_entropy` pair the source with the wrong trial at 7 or more trials and circularly shift each trial below that, because a few trials admit too few re-pairings for a calibrated null; `params['surrogate_scheme']` records which ran.
4. **Coupling, direction, delay and volume conduction**: invariants 7 and 8 of the router, [`skills/jnwb/SKILL.md`](../jnwb/SKILL.md) section 4, bind every operation here.

## 4. Minimal Workflow
```python
# Input: stochastic synthetic.
import jnwb
import numpy as np

rng = np.random.default_rng(42)
T = 500
X = rng.normal(size=T)
Y = np.zeros(T)
Y[1:] = 0.5 * X[:-1] + 0.5 * rng.normal(size=T-1)

res = jnwb.granger(X, Y, order=2, n_surrogates=50, rng=42)
assert res.x_to_y >= 0.0
```

## 5. Verification
- Granger asymmetry $F_{X \to Y} > F_{Y \to X}$ on synthetic unidirectional autoregressive simulations.
- PSI is positive for the driver and negative for the receiver **over a band wide enough to hold several frequency bins**, on broadband input rather than a sinusoid. On 2000 samples at 1 kHz with a 10 ms delay, a 20 Hz sine over `(19.0, 21.0)` gives `net = nan`, since the band holds one 2 Hz bin (`nperseg` of 500), while broadband noise over `(15.0, 30.0)` gives `net ≈ 0.93`. At one discrete frequency a delay and a constant phase offset are the same thing, so there is no slope to estimate; `docs/common_mistakes.md` section 7 runs this receipt.

## 6. Documentation
- [`docs/08_directed_connectivity_and_information.md`](../../docs/08_directed_connectivity_and_information.md)
