# Computational Complexity, CPU Parallelism & Acceleration Inventory

Upper bounds on time and peak memory for core primitives of `jnwb`, each justified by the algorithm the
implementation runs and the published reference for it. A bound is not a measurement: an exponent timed
below its bound agrees with it, and only one timed above it contradicts it. Timed exponents are a separate,
labelled benchmark (`artifacts/evidence/0.2.6/computational_order.md`, section 6), which cites rows here by
their `INV-` label and fits each exponent by least squares on log time against log size over at least three
input scales.

## 1. Symbol Definitions

- $C$: Number of channels / probe contacts.
- $T$: Number of time samples.
- $F$: Number of frequency bins ($N_{\text{perseg}} / 2 + 1$ or Morlet scales).
- $R$: Number of trials.
- $U$: Number of isolated single-units.
- $S$: Number of surrogates or bootstrap iterations.
- $N$: Number of conditions / stimuli.
- $D$: Number of features.
- $K$: Number of CV outer folds.
- $K_{\text{seg}}$: Number of Welch segments, $\approx T / (N_{\text{perseg}} - N_{\text{overlap}})$.
- $P$: Autoregressive model order.
- $E$: Element offset of the last selected element in a stored array ($\le$ its element count).

---

## 2. Big-O Complexity & Memory Bounds

| ID | Primitive | Module | Time upper bound | Peak memory upper bound | Algorithm | Reference |
|---|---|---|---|---|---|---|
| INV-01 | `complex_tfr` | `jnwb.tfr` | $\mathcal{O}(C \cdot F \cdot T \log T)$ | $\mathcal{O}(C \cdot F \cdot T)$ | FFT convolution with one complex Morlet wavelet per frequency | Torrence & Compo 1998 |
| INV-02 | `TFRAccumulator` | `jnwb.tfr_accumulator` | $\mathcal{O}(R \cdot C \cdot F \cdot T)$ | $\mathcal{O}(C \cdot F \cdot T)$ | One streaming update per trial; the $R$ trials are never held together | Welford 1962 |
| INV-03 | `compute_psd` | `jnwb.spectral` | $\mathcal{O}(C \cdot T \log N_{\text{perseg}})$ | $\mathcal{O}(C \cdot N_{\text{perseg}})$ | Welch: $K_{\text{seg}}$ windowed FFTs of length $N_{\text{perseg}}$, averaged | Welch 1967 |
| INV-04 | `wpli` | `jnwb.spectral` | $\mathcal{O}(T \log N_{\text{perseg}})$ | $\mathcal{O}(F \cdot K_{\text{seg}})$ | Segment FFTs, then a weighted sum of the imaginary cross-spectrum | Welch 1967; Nolte et al. 2004 |
| INV-05 | `phase_slope_index` | `jnwb.connectivity` | $\mathcal{O}(T \log N_{\text{perseg}} + K_{\text{seg}}^2 \cdot F)$ | $\mathcal{O}(F \cdot K_{\text{seg}})$ | Segment FFTs and the coherency slope; the default leave-one-segment-out jackknife recomputes the slope $K_{\text{seg}}$ times over $K_{\text{seg}} - 1$ segments, which is the quadratic term (`jackknife=False` drops it) | Nolte et al. 2008 |
| INV-06 | `granger` | `jnwb.connectivity` | $\mathcal{O}(T \cdot P^2 + P^3)$ | $\mathcal{O}(T \cdot P)$ | Bivariate VAR($P$) by ordinary least squares ($P \ll T$) | Granger 1969; Geweke 1982 |
| INV-07 | `transfer_entropy` | `jnwb.connectivity` | $\mathcal{O}(S \cdot T)$ | $\mathcal{O}(T)$ | Binned conditional mutual information, recomputed once per surrogate | Schreiber 2000 |
| INV-08 | `vflip` | `jnwb.laminar` | $\mathcal{O}(C \cdot F)$ | $\mathcal{O}(C \cdot F)$ | Relative-power difference across depth and its crossing | Mendoza-Halliday et al. 2024 |
| INV-09 | `xflip` | `jnwb.laminar` | $\mathcal{O}(C^2 \cdot T + S \cdot C^2)$ | $\mathcal{O}(C^2)$ | Pairwise channel correlation matrix, then a dynamic-programming boundary search per surrogate | Pearson correlation; dynamic programming |
| INV-10 | `zflip` | `jnwb.laminar` | $\mathcal{O}(C \cdot T \log N_{\text{perseg}} + S \cdot C \cdot F)$ | $\mathcal{O}(C \cdot F \cdot K_{\text{seg}})$ | Adjacent-channel wPLI and phase-slope regression, with surrogates | Welch 1967; Nolte et al. 2008 |
| INV-11 | `rdm` | `jnwb.rsa` | $\mathcal{O}(N^2 \cdot D)$ | $\mathcal{O}(N^2)$ | All pairwise distances between $N$ patterns of $D$ features | Kriegeskorte et al. 2008 |
| INV-12 | `rdm_similarity` | `jnwb.rsa` | $\mathcal{O}(N^2 \log N)$ | $\mathcal{O}(N^2)$ | Spearman correlation of two condensed vectors of length $N(N-1)/2$: a sort of each | Kriegeskorte et al. 2008 |
| INV-13 | `nested_cv_linear_svm` | `jnwb.decoding` | $\mathcal{O}(K \cdot N_{\text{C}} \cdot R^2 \cdot D)$ | $\mathcal{O}(R \cdot D)$ | Nested cross-validation over $N_{\text{C}}$ regularisation values; each fit is a linear SVM by coordinate descent | scikit-learn `LinearSVC` (liblinear) documentation |
| INV-14 | `stream_npz_array` | `jnwb.io` | $\mathcal{O}(E)$ | $\mathcal{O}(\text{slice volume})$ | One forward pass over the member up to its last selected element, discarding what is skipped in fixed-size chunks; a compressed member cannot be seeked, so time is bounded by position, not by what is kept | ZIP and `.npy` format specifications |
---

## 3. CPU Parallelism & Concurrency

- **Speed Knob**: `n_jobs` parameter (default 1) forwards to `jnwb._parallel.parallel_map`.
- **Nested Oversubscription Prevention**: Parallel loops over channels or independent conditions set thread counts to avoid oversubscribing BLAS/OpenMP backend pools.
- **RNG Child Hygiene**: Parallel surrogate/permutation workers instantiate child streams via `np.random.SeedSequence(seed).spawn(n_workers)`, preventing correlated pseudo-random streams.

---

## 4. Hardware Acceleration Classification

| Primitive | Classification | Justification |
|---|---|---|
| `complex_tfr` | `CUDA_AVAILABLE` | CuPy FFT accelerates large channel/frequency tensors |
| `band_power` / `_welch_csd_gpu` | `CUDA_AVAILABLE` | CuPy implementation with exact SciPy parity and CPU fallback |
| `jrsa` (`_cka`, `_rv`) | `CUDA_AVAILABLE` | Large matrix dot products benefit from GPU linear algebra |
| `wpli` | `CUDA_AVAILABLE` | Segment FFT and tensor reduction implemented on CuPy with CPU fallback |
| `nested_cv_linear_svm` | `CPU_ONLY_JUSTIFIED` | Scikit-learn LinearSVC / liblinear is optimized for CPU |
| `vflip` / `xflip` / `zflip` | `CPU_ONLY_JUSTIFIED` | Channel counts ($C \le 128$) are small; host-device transfer cost exceeds compute benefit |
