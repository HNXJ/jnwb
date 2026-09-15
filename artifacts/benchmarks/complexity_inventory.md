# Computational Complexity, CPU Parallelism & Acceleration Inventory

Formal Big-O time and peak memory bounds for core primitives in `jnwb`, derived from mathematical algorithms and verified against empirical heap allocations.

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

---

## 2. Big-O Complexity & Memory Bounds

| Primitive | Module | Big-O Time | Peak RAM Memory | Notes & Dominant Kernel |
|---|---|---|---|---|
| `complex_tfr` | `jnwb.tfr` | $\mathcal{O}(C \cdot F \cdot T \log T)$ | $\mathcal{O}(C \cdot F \cdot T)$ | FFT-based complex Morlet convolution |
| `TFRAccumulator` | `jnwb.tfr_accumulator` | $\mathcal{O}(R \cdot C \cdot F \cdot T)$ | $\mathcal{O}(C \cdot F \cdot T)$ | Streaming Welford algorithm; avoids storing $R$ trials |
| `compute_psd` | `jnwb.spectral` | $\mathcal{O}(C \cdot T \log N_{\text{perseg}})$ | $\mathcal{O}(C \cdot N_{\text{perseg}})$ | Welch averaged periodogram across segments |
| `wpli` | `jnwb.spectral` | $\mathcal{O}(T \log N_{\text{perseg}})$ | $\mathcal{O}(F \cdot K_{\text{seg}})$ | STFT imaginary cross-spectrum aggregation |
| `phase_slope_index` | `jnwb.connectivity` | $\mathcal{O}(T \log N_{\text{perseg}} + F)$ | $\mathcal{O}(F \cdot K_{\text{seg}})$ | Cross-spectral coherency slope |
| `granger` | `jnwb.connectivity` | $\mathcal{O}(T \cdot P^2 + P^3)$ | $\mathcal{O}(T \cdot P)$ | Bivariate VAR(P) OLS regression ($P \ll T$) |
| `transfer_entropy` | `jnwb.connectivity` | $\mathcal{O}(S \cdot T)$ | $\mathcal{O}(T)$ | Discrete binning & Markov lag conditional MI |
| `vflip` | `jnwb.laminar` | $\mathcal{O}(C \cdot F)$ | $\mathcal{O}(C \cdot F)$ | Spectrolaminar difference & zero-crossing |
| `xflip` | `jnwb.laminar` | $\mathcal{O}(C^2 \cdot T + S \cdot C^2)$ | $\mathcal{O}(C^2)$ | Pairwise correlation matrix & dynamic programming |
| `zflip` | `jnwb.laminar` | $\mathcal{O}(C \cdot T \log N_{\text{perseg}} + S \cdot C \cdot F)$ | $\mathcal{O}(C \cdot F \cdot K_{\text{seg}})$ | Adjacent wPLI, phase slope regression & surrogates |
| `rdm` | `jnwb.rsa` | $\mathcal{O}(N^2 \cdot D)$ | $\mathcal{O}(N^2)$ | Pairwise distance computation (condensed/square) |
| `rdm_similarity` | `jnwb.rsa` | $\mathcal{O}(N^2 \log(N^2))$ | $\mathcal{O}(N^2)$ | Spearman rank correlation of condensed vectors |
| `nested_cv_linear_svm` | `jnwb.decoding` | $\mathcal{O}(K \cdot N_{\text{C}} \cdot R^2 \cdot D)$ | $\mathcal{O}(R \cdot D)$ | Stratified nested cross-validated linear SVM |
| `stream_npz_array` | `jnwb.io` | $\mathcal{O}(\text{slice volume})$ | $\mathcal{O}(\text{slice volume})$ | Direct chunk/slice I/O without full RAM load |

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
