# xFLIP Empirical Calibration & Operating Characteristics Receipt

> **Provenance (added in 0.2.4).** The tables below were produced under 0.2.3 and no
> generator script was retained, so they cannot be regenerated. `xflip` changed in 0.2.4:
> it now rejects input containing a zero-variance channel and reports that channel's
> correlations as NaN, instead of returning a correlation of 0. The null families here
> contain no zero-variance channel, so the rates are not expected to move, but that is an
> argument rather than a measurement.
>
> What is measured against the shipped estimator is `tests/test_xflip_calibration.py`,
> which recomputes false-positive rates on the white-noise, AR, periodic-common-response
> and smooth-gradient nulls, and recovery and localization on equal, unequal and
> three-block alternatives and across channel counts, on every test run. Treat that as the
> authority on current operating characteristics and this file as a historical record.
> Unlike `vflip_calibration_0.2.4_raw.json`, this receipt is not bound to the estimator by
> a source hash.

## 1. Null Ensemble False Positive Rates (alpha = 0.05)

| Null Family | N Seeds | False Positive Rate | Median p-value | Min p-value | Max p-value | Median Modularity (Q) |
|---|---|---|---|---|---|---|
| `white_noise` | 30 | 0.000 | 0.4902 | 0.0784 | 1.0000 | 0.0102 |
| `ar_noise` | 30 | 0.033 | 0.3922 | 0.0196 | 0.9412 | 0.0550 |
| `periodic_common_response` | 30 | 0.000 | 0.9020 | 0.7647 | 0.9804 | 0.0066 |
| `smooth_spatial_gradient` | 30 | 0.000 | 0.0196 | 0.0196 | 0.0196 | 0.3271 |

## 2. Alternative Ensemble Recovery & Localization Accuracy

### A. SNR / Within-Block Correlation Sweep (N=16, Equal Blocks [8, 8])

| Within Corr (rw) | True Positive Rate | Median Localization Error (ch) | Max Error (ch) | Median Modularity (Q) |
|---|---|---|---|---|
| 0.2 | 0.900 | 0.00 | 0.00 | 0.1467 |
| 0.4 | 1.000 | 0.00 | 0.00 | 0.3426 |
| 0.6 | 1.000 | 0.00 | 0.00 | 0.5401 |
| 0.8 | 1.000 | 0.00 | 0.00 | 0.7406 |

### B. Unequal Block Partitioning

| Block Sizes | True Boundary | True Positive Rate | Median Localization Error (ch) | Median Modularity (Q) |
|---|---|---|---|---|
| (4, 12) | 4 | 1.000 | 0.00 | 0.5920 |
| (12, 4) | 12 | 1.000 | 0.00 | 0.5975 |
| (6, 18) | 6 | 1.000 | 0.00 | 0.6046 |

### C. Three-Block Laminar Compartment Partitioning

| Block Sizes | True Boundaries | True Positive Rate | Median Error b1 (ch) | Median Error b2 (ch) | Median Modularity (Q) |
|---|---|---|---|---|---|
| (6, 6, 6) | (6, 12) | 1.000 | 0.00 | 0.00 | 0.6997 |
| (4, 8, 4) | (4, 12) | 1.000 | 0.00 | 0.00 | 0.6955 |

### D. Channel Count Scaling Sweep (Equal Blocks, rw=0.7, rb=0.1)

| N Channels | True Positive Rate | Median Localization Error (ch) | Median Modularity (Q) |
|---|---|---|---|
| 8 | 1.000 | 0.00 | 0.5958 |
| 12 | 1.000 | 0.00 | 0.6074 |
| 16 | 1.000 | 0.00 | 0.6142 |
| 24 | 1.000 | 0.00 | 0.5981 |
| 32 | 1.000 | 0.00 | 0.5860 |
| 48 | 1.000 | 0.00 | 0.5976 |
| 64 | 1.000 | 0.00 | 0.6008 |

## 3. Determinism & Randomness Hygiene

- Same-seed repeated runs bitwise identical: `True`
- Different-seed modularity invariance (deterministic estimator): `True`
- Different-seed Monte Carlo p-value: mean = `0.0196`, std = `0.0000` (within theoretical binomial sampling interval).
