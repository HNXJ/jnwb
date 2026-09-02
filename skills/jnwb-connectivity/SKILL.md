---
name: jnwb-connectivity
description: Directed connectivity, bivariate Granger causality, phase slope index
  (PSI), transfer entropy, and graph measures.
---

# `jnwb-connectivity` — Directed Connectivity & Functional Coupling

## 1. Trigger
Activate this skill when quantifying directional coupling, lag asymmetries, Granger causality, phase slope index, or transfer entropy across brain regions or channels.

## 2. Task-to-Primitive Routing Matrix
- `jnwb.granger(X, Y, order, n_surrogates, seed)`: Time-domain bivariate Granger causality with time-shift surrogate significance.
- `jnwb.granger_spectral(X, Y, fs, order, freqs)`: Frequency-resolved spectral Granger causality.
- `jnwb.phase_slope_index(X, Y, fs, bands)`: Phase Slope Index (PSI) quantifying frequency-dependent driver/receiver lag.
- `jnwb.transfer_entropy(X, Y, k=1, l=1, n_surrogates=...)`: Non-linear information-theoretic transfer entropy.
- `jnwb.directed_connectivity(signals, fs, method="granger"|"psi"|"te")`: Multi-channel pairwise directed connectivity matrix.
- `jnwb.directed_network(adj_matrix, ...)`: Graph-theoretic network metrics (in-degree, out-degree, asymmetry index).

## 3. Invariants & Safeguards
1. **Strict Epistemic Language**: Granger causality, PSI, and Transfer Entropy measure **temporal-lag asymmetry (predictive directionality)** under an observational model. Never use causal verbs ("region A drives region B causally") for observational time-series metrics.
2. **Stationarity & Pre-filtering**: Time-domain Granger requires wide-sense stationary inputs; demean and detrend signals prior to model fitting.
3. **Surrogate Null Construction**: Evaluate significance using time-shift surrogates that destroy temporal alignment while preserving autocorrelation.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
T = 500
X = rng.normal(size=T)
Y = np.zeros(T)
Y[1:] = 0.5 * X[:-1] + 0.5 * rng.normal(size=T-1)

res = jnwb.granger(X, Y, order=2, n_surrogates=50, seed=42)
assert res.x_to_y >= 0.0
```

## 5. Verification
- Verify Granger asymmetry $F_{X \to Y} > F_{Y \to X}$ on synthetic unidirectional autoregressive simulations.
- Verify PSI returns positive slope for driver and negative for receiver.

## 6. Canonical Documentation Links
- [`docs/08_directed_connectivity_and_information.md`](../../docs/08_directed_connectivity_and_information.md)
