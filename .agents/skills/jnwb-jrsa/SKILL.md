---
name: jnwb-jrsa
description: |
  Joint Relationship and Spectral Analysis (JRSA) engine connectivity guidelines and refactoring roadmap.
---

# Skill: jnwb-jrsa — Joint Relationship and Spectral Analysis Reference


Unified reference for the Joint Relationship and Spectral Analysis (`jrsa`) engine inside `jnwb`.

## Public API

`jrsa(x1, x2=None, adim=-1, labels=None, align="auto", align_mode="fraction", reduction=None, metric="rsa", lag=0, window=None, sliding=False, normalize=False, standardize=False, detrend=False, nan_policy="omit", stats=True, permutations=1000, bootstrap=0, correction="fdr_bh", alpha=0.05, alternative="two-sided", backend="auto", device="auto", n_jobs=-1, batch_size=None, random_state=None, return_type="result", return_null=False, return_input=False, verbose=False, **kwargs)`

Returns a `JRSAResult` container wrapping `(value, statistic, effect, p, q, df, ci, ...)` fields.

## Supported Metrics & Return Conventions

All metric dispatch functions `_metric(x1, x2, axis=-1, **kwargs)` must return exactly five values: `(value, statistic, effect, p, df)`.
- **pearson**: Pearson product-moment correlation (CPU/GPU-accelerated).
- **spearman**: Spearman rank correlation (CPU/GPU rank-transform + Pearson).
- **kendall**: Kendall's tau (CPU fallback).
- **cosine**: Cosine similarity (CPU/GPU vectorized dot product).
- **rsa**: Representational Similarity Analysis RDM correlation (operating directly on condensed upper-triangular vector values).
- **cka**: Centered Kernel Alignment (linear complexity optimization $O(m d^2)$ when $d \ll m$).
- **rv**: RV matrix correlation coefficient (linear complexity optimization $O(m d^2)$ when $d \ll m$).
- **hsic**: Hilbert-Schmidt Independence Criterion (efficient centering avoiding dense $m \times m$ matrix allocations). Assumes symmetric kernel matrices.
- **distance_correlation**: Distance correlation (Székely & Rizzo).
- **mutual_information**: Mutual information via joint histogram estimator.
- **procrustes**: Procrustes shape alignment similarity.
- **granger**: Granger causality F-statistic (x2 → x1) with best lag selection by OLS AIC.
- **transfer_entropy**: First-order Transfer entropy (x2 → x1) via plug-in histogram estimator.
- **phase_slope**: Phase Slope Index (PSI) preserving magnitude scale (coherence-normalized Nolte formulation).

## Correctness & Data Conventions

- **NaN Omit**: Joint listwise exclusion of NaN indices across paired arrays on the last axis before metric computation.
- **Multi-Lag**: Stacking shifted temporal lag rolling inputs into a `(n_lags, ...)` shape. Permutation/bootstrap p-values are not lag-segregated inside the permutation helper. A lag loop must wrap stats blocks in `jrsa()` for proper lag-segregated p-values.
- **HSIC Symmetry**: Assumes symmetric kernels ($K^T = K$) and asserts symmetry to prevent silent wrong calculations.
- **Granger AIC**: Extracts unrestricted model AIC from statsmodels results `res[lag][1][1].aic`. Loops defensively to preserve the best-found lag on exceptions.

## GPU Execution Safety

- **Backend Dispatch**: Use `_get_xp(arr)` namespace helper to resolve `cupy` or `numpy` depending on the input array type.
- **RNG Seeding**: Use `cp.random.permutation` and `cp.random.randint` on-device to avoid host-device copying inside loop iterations.

## Dead Code Register

- `_compute_statistics` is a no-op dead stub returning the raw value.
- `_stack_batches` is defined but never called; `batch_size` remains a cosmetic parameter.

## Refactoring & Cleanup Roadmap

To bring the `jrsa` engine to perfect state:
1. **Consolidate CPU Duplicated Paths**:
   * Currently, `jnwb/jrsa.py::_pearson` and `_spearman` duplicate correlation math. Rewrite these to delegate to the unified `StatisticalAnalysis.correlate` method for CPU arrays.
2. **Remove Dead Stubs**:
   * Delete the no-op `_compute_statistics` function completely.
   * Remove the unused `_stack_batches` function and standardise or remove the inactive `batch_size` parameter from the public API.
3. **Refactor Dimension Reduction**:
   * Replace the duplicated 80-line dimension reduction if/elif blocks for `x1` and `x2` inside `jrsa()` with a clean unified function or an `_OPS` dispatch table.

