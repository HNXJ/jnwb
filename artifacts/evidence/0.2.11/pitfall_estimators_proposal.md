# Pitfall estimators: proposal (item 11-04)

Four estimators that `tests/test_connectivity_pitfalls.py` names as gaps. Each entry gives the
reference, the signature, the check that will hold it, and the choice to rule. References were
matched on Crossref on 2026-10-21. Each recommended shape widens an existing call (AGENTS.md
§4.7) and adds no public symbol.

## 1. Nonparametric spectral Granger causality

- Reference: Dhamala, M., Rangarajan, G., & Ding, M. (2008). Estimating Granger causality from
  Fourier and wavelet transforms of time series data. *Phys. Rev. Lett.* 100, 018701.
  doi:10.1103/PhysRevLett.100.018701. Factorization: Wilson, G. T. (1972). The factorization of
  matricial spectral densities. *SIAM J. Appl. Math.* 23, 420-426. doi:10.1137/0123044.
- Method: the 2x2 cross-spectral matrix S(f) is estimated from the data (Welch segments, the
  `nperseg`/`noverlap` of `cross_area_coherence`), factorized by Wilson's iteration into
  S = H Σ H*, and Geweke's measure is computed from H and Σ as `granger_spectral` does now.
- Shape A (recommended): `granger_spectral(X, Y, fs, ..., method="parametric" | "nonparametric",
  nperseg=None, noverlap=None, max_iter=500, tol=1e-10)`. `order`, `max_lag` and `criterion`
  are refused under `"nonparametric"`. `diagnostics` gains `factorization_iterations` and
  `factorization_residual` (max |S - H Σ H*| / max |S|). If the iteration does not converge,
  the call raises; it never returns the last iterate.
- Shape B: a new `granger_spectral_nonparametric(X, Y, fs, nperseg=None, noverlap=None,
  bands=None, max_iter=500, tol=1e-10, n_surrogates=0, rng=Default(0), time_axis=-1)`.
- Identity check: on a simulated bivariate VAR(p) with x→y coupling only, the nonparametric
  spectrum agrees with the parametric one fitted at the true order p. The tolerance is the
  median relative difference over frequencies, measured at three seeds before it is pinned. A
  y→x spectrum stays at the surrogate floor.

## 2. Time-reversed Granger control

- References: Haufe, S., Nikulin, V. V., Müller, K.-R., & Nolte, G. (2013). A critical
  assessment of connectivity measures for EEG data: a simulation study. *NeuroImage* 64,
  120-133. doi:10.1016/j.neuroimage.2012.09.036. Winkler, I., Panknin, D., Bartz, D., Müller,
  K.-R., & Haufe, S. (2016). Validity of time reversal for testing Granger causality. *IEEE
  Trans. Signal Process.* 64, 2746-2760. doi:10.1109/TSP.2016.2531628.
- Decision rule (Winkler et al. 2016): net flow D = F(x→y) - F(y→x) on the data and D_r on the
  time-reversed data, with the same order. The direction is **strong** when D and D_r have
  opposite signs and both are significant under the surrogate null. A noise or power
  asymmetry leaves the sign unchanged under reversal, and then the direction is **not
  supported**. Any other case is **weak**.
- Shape A (recommended): `granger(..., reversal_control=False)`. When it is True,
  `diagnostics` gains `net`, `net_reversed`, `p_net`, `p_net_reversed` and
  `reversal_verdict` in {"strong", "weak", "not supported"}. It needs `n_surrogates > 0` and is
  refused otherwise, since the rule needs both p-values.
- Shape B: a new `granger_reversal_control(X, Y, order="auto", n_surrogates=199,
  rng=Default(0), **granger_kwargs) -> dict`.
- Check: `test_an_uncoupled_pair_gains_a_reported_direction_from_the_noise_asymmetry`'s pair,
  order 8, 6x noise on y, gives "not supported". The coupled pair at lag 8 gives "strong" at 10
  of 10 seeds.

## 3. Partial coherence conditioned on a third signal

- Reference: Dahlhaus, R. (2000). Graphical interaction models for multivariate time series.
  *Metrika* 51, 157-172. doi:10.1007/s001840000055.
- Method: G(f) = S(f)^-1 of the 3x3 cross-spectral matrix of (x, y, z). The partial coherence is
  |G_xy|² / (G_xx G_yy), from the same Welch segments as the unconditioned coherence.
- Shape A (recommended): `cross_area_coherence(lfp_area1, lfp_area2, ..., condition_on=None)`,
  where `condition_on` is one array or a list of arrays shaped like the inputs. With it, the
  result reports `partial_coherence` per band beside `coherence`, and the surrogate null
  shifts `lfp_area2` as now. A singular S(f) at any frequency raises with that frequency.
- Shape B: a new `partial_coherence(x, y, z, fs, nperseg=None, noverlap=None, freq_bands=None,
  n_surrogates=50, rng=DEFAULT_SEED)`.
- Check: a common driver z feeds x and y with no x-y path. The coherence is significant in the
  driven band and the partial coherence sits at the surrogate floor. With z independent noise,
  the partial coherence equals the coherence within the floor.

## 4. A bias floor from randomly paired epochs

- References: Maris, E., Schoffelen, J.-M., & Fries, P. (2007). Nonparametric statistical
  testing of coherence differences. *J. Neurosci. Methods* 163, 161-175.
  doi:10.1016/j.jneumeth.2007.02.011. Bastos, A. M., & Schoffelen, J.-M. (2016). A tutorial
  review of functional connectivity analysis methods and their interpretational pitfalls.
  *Front. Syst. Neurosci.* 9, 175. doi:10.3389/fnsys.2015.00175.
- Pairing scheme: a uniform random derangement of trial indices, so epoch i of x meets epoch
  π(i) ≠ i of y. It is drawn `n_pairings` times from `rng`. The floor is the metric's mean and
  95th percentile over the pairings. It needs 2 or more trials and is refused below that.
  The result records `pairing_scheme="derangement"`, `n_pairings` and
  `surrogate_seed_entropy`, as the existing surrogates do.
- Shape A (recommended): `cross_area_coherence(..., bias_floor=None | "paired_epochs",
  n_pairings=200)` for trial-shaped input. The result reports `floor_mean` and `floor_q95` per
  band.
- Shape B: a new `epoch_pairing_floor(metric, x_trials, y_trials, n_pairings=200,
  rng=Default(0), **metric_kwargs) -> dict`, over any pairwise metric.
- Check: with independent trials the observed coherence lies at or below floor_q95 at 19 of 20
  seeds. With a planted shared rhythm it exceeds floor_q95. Two calls with `rng=None` give
  different pairings.

## Rulings needed

One per estimator: shape A (a keyword on an existing call) or shape B (one new public symbol).
