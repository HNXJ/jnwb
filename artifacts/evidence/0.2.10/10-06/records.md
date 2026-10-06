# 10-06 calibration records

Worktree `C:/workspace/jnwb-lanes/g-10-06`, branch `lane-g-1006`, baseline `32e0a3cc` plus the
10-06 working changes. Each script asserts `jnwb` imports from the worktree, and each `.out`
is its full output. Seeds are `default_rng(s)` for `s` in `0..n-1`.

## PSI default segment count (D10(c))

`calibrate_psi_default_segments.py <worktree> 4000` -> `psi_default_segments.out`. One trial of
2000 samples at 1 kHz; lead p is the jackknife t test, rate is P(p < 0.05), se binomial.

| Scenario | Bands | Old `n//4` (7 segments) | New default (20 segments) |
|---|---|---|---|
| zero-lag mixing, no lead | 5-100 Hz | 0.0173 (0.0021) | 0.0573 (0.0037) |
| zero-lag mixing, no lead | whole | 0.0080 (0.0014) | 0.0227 (0.0024) |
| independent | 5-100 Hz | 0.0112 (0.0017) | 0.0043 (0.0010) |
| independent | whole | 0.0115 (0.0017) | 0.0063 (0.0012) |
| 5-sample lead, noise sd 1 | 5-100 Hz | 0.5920 (0.0078) | 1.0000 |
| 5-sample lead, noise sd 1 | whole | 1.0000 | 1.0000 |

Observed: the new default moves the mixing rate over 5-100 Hz to 0.057, inside the 0.06 to
0.08 the docstring states for segment-level jackknives, and raises detection of the lead from
0.59 to 1.00. The jackknife still leaves out one segment (P-227, not changed here).

## jrsa block bootstrap coverage (IB-44): not met, not shipped

`calibrate_jrsa_block_bootstrap.py <worktree> 1000 pearson 200:block:20 500:block:20
500:block:50 1000:block:50 500:iid:-` -> `jrsa_block_bootstrap.out`. Independent AR(1) pairs,
coefficient 0.9; coverage is the share of 95% percentile intervals holding the true 0. The
interval was a moving-block bootstrap (Kunsch 1989) of `block_len` samples, x1 and x2 resampled
together, 999 draws.

| n | Resampling | Coverage (se) | Mean width |
|---|---|---|---|
| 200 | blocks of 20 | 0.846 (0.011) | 0.591 |
| 500 | blocks of 20 | 0.883 (0.010) | 0.423 |
| 500 | blocks of 50 | 0.886 (0.010) | 0.432 |
| 1000 | blocks of 50 | 0.913 (0.009) | 0.333 |
| 500 | single samples (`null='iid'`) | 0.447 (0.016) | 0.168 |

Observed: the moving-block percentile interval undercovers at every size tried, by 4 to 10
points. The code was reverted and the refusal stands; the choice of interval is returned for a
ruling.

## Transfer entropy excess by n under zero-lag mixing

`te_excess_by_n.py <worktree> 1500 500 2000 4000 8000 16000` -> `te_excess_by_n.out`.
`x = w + 0.5 e1`, `y = w + 0.5 e2`, `w` white; quantile bins 4, k = l = 1, 199 surrogates,
X -> Y. The script rebuilds each null from the recorded child seed with the function's own
surrogate scheme; its p matched the function's in every pair (max difference 0).

| n | P(p < 0.05) (se) | Plug-in excess, chi-square units (se) | Occupied cells, data / surrogates | Miller-Madow shift |
|---|---|---|---|---|
| 500 | 0.0340 (0.0047) | -1.39 (0.23) | 55.55 / 63.99 | +7.54 |
| 2000 | 0.0527 (0.0058) | +0.62 (0.22) | 60.36 / 64.00 | +3.55 |
| 4000 | 0.0687 (0.0065) | +1.23 (0.23) | 62.33 / 64.00 | +1.66 |
| 8000 | 0.0453 (0.0054) | +0.45 (0.22) | 63.65 / 64.00 | +0.35 |
| 16000 | 0.0353 (0.0048) | +0.06 (0.21) | 63.98 / 64.00 | +0.02 |

Excess is `2 N ln 2` times the observed plug-in TE minus the mean plug-in TE of its
surrogates: 0 when the null is centred on the observation's distribution.

Observed: the rejection rate follows the excess in sign and size, peaking with it at n = 4000,
and both vanish as the data's joint table fills the 64 cells the surrogates occupy. Inferred,
not tested: below saturation the data's dependent (Y_past, X_past) table occupies fewer cells
and carries a smaller plug-in bias than its surrogates (negative excess, conservative); near
saturation its unequal cell probabilities carry a larger second-order bias (positive excess,
liberal), which decays as 1/N.

## bias_corrected_* under mixing

`probe_bias.py` (40 seeds, n 2000, 49 surrogates; output quoted in the `transfer_entropy`
docstring): TE `bias_corrected_x_to_y` mean 0.0014 bits (sd 0.0033) under mixing, 0.0001
independent; Granger 0.00015 and 0.00009.
