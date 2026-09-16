# 11. Extending `jnwb` & Developer Guide

The rules for maintaining, extending and testing `jnwb`. For setup, branches, the checks to run and how a release is cut, see [`CONTRIBUTING.md`](https://github.com/HNXJ/jnwb/blob/main/CONTRIBUTING.md).

---

## 1. Extension Rule

A new function, class, or constant belongs in `jnwb` **only when it is generic across neuroscience/NWB datasets** and has a clear mathematical or data-processing meaning independent of a particular experiment.

```
                          [ Generic Mathematical / Signal / NWB Primitive ]
                                                  │
                         Is it dataset-agnostic and experiment-independent?
                                          ┌───────┴───────┐
                                         YES              NO
                                          │               │
                                   ┌──────▼──────┐ ┌──────▼──────────────┐
                                   │ Add to jnwb │ │ Keep in downstream  │
                                   │    core     │ │ project / analysis  │
                                   └─────────────┘ └─────────────────────┘
```

- **In Core (`jnwb/`)**: Generic Morlet wavelets, PSD estimation, spike-LFP phase locking, temporal alignment, FDR multiple testing, linear SVM decoding, causal smoothing, NWB file inspection and channel addressing.
- **Outside Core**: Experiment-specific condition identifiers (e.g. task sequence codes, stimulus condition names), task timing protocols, custom area grouping rules, study-specific publication figures, biological hypothesis interpretations, and ad-hoc analysis notebooks.

---

## 2. Code Rules & Quality Standards

All code in `jnwb` must satisfy the following implementation standards:

1. **Small Composable Primitives**: Functions perform one well-defined operation. Complex workflows are composed from modular primitives rather than monolithic scripts.
2. **Explicit Dimensions, Units & Coordinates**: Always specify physical units (e.g. `fs: float` in Hz, time in seconds, frequencies in Hz). Never confuse array indices with physical coordinate values.
3. **Stable Terminology**: Use standardized parameter names across modules (`fs` or `sampling_rate`, `time_window`, `freq_range`, `alpha`, `rng`).
4. **Typed Public Signatures**: Type-annotate public function arguments and return types.
5. **Deterministic Behavior & Explicit RNG**: Functions requiring stochasticity (permutation, bootstrap, cross-validation) must accept an optional `rng: Optional[Union[np.random.Generator, int]] = None` and instantiate a local generator via `np.random.default_rng(rng)`. **Never mutate global state** (`np.random.seed()`).
6. **No Hidden Filesystem Assumptions**: Never hardcode relative paths, machine-specific drive letters, or external network dependencies in library functions.
7. **No Silent Numerical Clipping / Censoring**: Never silently clamp, filter, or discard invalid values unless explicitly requested by a parameter.
8. **Explicit Boundary / Failure States**: When a fit hits parameter bounds or optimization fails, return explicit status flags (e.g. `bound_status: "lower" | "upper" | None`) rather than masking errors as valid interior solutions.
9. **Cost-Justified Vectorization & Streaming**: Vectorize NumPy/SciPy operations where profiling shows a bottleneck; use streaming accumulators (`TFRAccumulator`) for memory-intensive multi-trial arrays.
10. **Behavior-Preservation Optimization**: Never refactor or optimize code without existing behavioral tests passing before and after.

---

## 3. Public API Rule

The top-level `jnwb` namespace is intentionally curated.

$$\text{New Public Symbol} \iff \text{Implementation} + \text{Tests} + \text{Documentation} + \text{Skill Routing}$$

- **Internal vs. Public**: Helper functions, intermediate utilities, and implementation details must remain private (prefixed with `_`) and un-exported in `__all__`.
- **No Inventions**: Never document or export unverified symbols.
- **Breaking Changes**: Breaking changes to public signatures require an explicit deprecation cycle with informative `DeprecationWarning` or `FutureWarning` notices before removal.

---

## 4. Testing Rule

Every module must be protected by deterministic test coverage in `tests/`. Tests must include diagnostic probes covering:

- **Identity**: Identity inputs yield expected mathematical identities ($X = X$, correlation of identical signals = 1).
- **Sign**: Inversions, negative latencies, or anti-correlations yield correct signs.
- **Scale**: Linear scaling of input signals propagates mathematically through operators.
- **Shape**: Correct multi-dimensional output array shapes across single-trial, multi-trial, single-channel, and multi-channel configurations.
- **Boundary**: Edge cases, zero inputs, single-element arrays, Nyquist boundaries, and parameter bounds.
- **State Isolation**: Guarantee that function execution leaves global RNG, global matplotlib state, and filesystem state untouched.
- **Composition**: Output of upstream primitives safely feeds into downstream analyzers.
- **Numerical Stability**: Safeguards against divide-by-zero, NaN propagation, ill-conditioned matrices, and float precision overflow.
- **Regression Tests**: Every corrected bug or edge case must be accompanied by an adversarial regression test.

---

## 5. Documentation Rule

- **Truth Precedence**: Code and direct empirical receipts define implemented behavior. Documentation must describe actual behavior without claiming stronger scientific capabilities than what is implemented and verified.
- **Lockstep Updates**: Any modification to a public symbol must update both the relevant documentation guide (`docs/`) and repository skill (`skills/`) in the same commit.
- **Warning-Free Builds**: The documentation must compile with zero warnings:
  ```bash
  python scripts/docs_build.py
  ```

---

## 6. Repository Root Freeze & `artifacts/` Policy

To maintain a clean, distributable repository structure, the repository root is **strictly frozen** to files and directories required for packaging, build, CI, documentation, tests, source, canonical skills, and core repository metadata:

$$\boxed{\text{New root entry requires demonstrated root necessity}}$$

Otherwise, files must be placed under `artifacts/`, `docs/`, `skills/`, `scripts/`, `tests/`, or the appropriate package directory.

### Repository Hierarchy
```text
jnwb/
├── jnwb/          # scientific implementation
├── tests/         # mechanical correctness & regression gates
├── docs/          # scientific + developer documentation
├── skills/        # reusable task procedures
├── scripts/       # deterministic repository tooling
├── artifacts/     # non-root work products, benchmarks, todo stack
└── root           # frozen package/repository control surface
```

### Permitted Root Entries (Allowlist)
- **Source & Tests**: `jnwb/`, `tests/`, `examples/`, `docs/`, `skills/`, `scripts/`
- **Configuration & Metadata**: `pyproject.toml`, `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore`, `mkdocs.yml`, `.readthedocs.yaml`, and the repository's policy files

The authoritative list is `ALLOWED_ROOT_DIRS` / `ALLOWED_ROOT_FILES` in `scripts/harness_gate.py`, enforced by Gate 4.
- **CI / VCS**: `.git/`, `.github/`
- **Repository Artifact Container**: `artifacts/`

### `artifacts/` Policy
The `artifacts/` directory is the canonical location for non-package, repository-associated artifacts that should not occupy root:

```text
artifacts/
├── todo_stack.md    # Remaining work, grouped by the version that carries it
├── benchmarks/      # Performance profiles, timing benchmarks, scalability receipts
├── data/            # Small fixtures and derived tables
├── developer/       # Developer work products
└── scratch/         # Disposable developer scripts, temporary test data (gitignored)
```

- **Rule**: Temporary scripts, test data, and ad-hoc exports must be placed in `artifacts/scratch/` or ignored via `.gitignore`, never committed to root.

---

## 7. Core Scientific Invariants

Every contributor adheres to these scientific invariants:

1. **Signal Class Independence**: SUA/SPK, MUA, and LFP represent physically distinct observables. Never pool features across modalities without explicit namespace tags.
2. **Estimand Disambiguation**: Clearly distinguish between prevalence, magnitude, decodable information, and biophysical mechanism.
3. **Causal & Directional Verbs**: $\text{Association} \ne \text{Directionality} \ne \text{Causality}$. Metrics like Granger causality or phase slope index measure temporal predictive asymmetry, not physical perturbation causality.
4. **Logarithmic Estimand Clarity**: Explicitly distinguish arithmetic mean of raw power ($\mathbb{E}[P]$, physical power conservation) from mean of logarithmic/decibel power ($\mathbb{E}[\log P]$, geometric mean / log-normal central tendency). Do not conflate the two estimands or treat raw-power averaging as an unconditional universal requirement without declaring the estimand.
5. **Unit of Inference**: Always declare whether statistical degrees of freedom reside at the unit, channel, trial, or session level.
6. **Valid Nulls**: A valid null is an empirical finding. Never alter test windows or parameters to artificially force statistical significance.
7. **No Synthetic Science**: Never present synthetic or dummy data as real electrophysiological observations.
8. **Scientific Vocabulary & Methodological Distinctions**: Prefer direct, compact, quantitative scientific terminology (`result`, `test`, `analysis`, `table`, `figure`, `method`, `limit`, `condition`) over process/governance jargon. Preserve critical distinctions: response magnitude does not imply temporal precision; detecting an effect does not by itself establish precise timing or an admissible latency; distinguish measurement precision, latency, estimator disagreement, and boundary censoring; descriptive lower-level percentages do not substitute for hypothesis tests at the declared higher-level inferential unit; association or directionality metrics do not establish physical causality.

---

## 8. Standard Development Flow

```
1. Inspect       Audit baseline state, locate input receipts, establish acceptance criteria.
       │
2. Define        Formulate exact mathematical semantics and parameter constraints.
       │
3. Implement     Implement the smallest sufficient change in jnwb/.
       │
4. Probe         Write diagnostic & adversarial tests in tests/ (identity, boundary, stability).
       │
5. Test Full     Run pytest tests/ ensuring zero regressions.
       │
6. Reconcile     Update docs/ and skills/ in lockstep with code changes.
       │
7. mkdocs strict Verify warning-free documentation compilation.
       │
8. Harness Gate  Execute python scripts/harness_gate.py.
       │
9. Seal & Push   Verify git status, stage exact paths, push to dev, delete the finished
                 item from artifacts/todo_stack.md.
```

---

## 9. 0.2 API Specifications & Frozen Rules

This section fixes the architectural and numerical contracts for all planned 0.2 minor releases (0.2.1 through 0.2.3) prior to implementation, resolving item `0.2.0-07`.

### 9.1 Cross-Cutting Architectural Invariants

Every operation added in 0.2 conforms to the following universal library conventions:

#### 1. RNG Convention
- Functions consuming stochasticity accept an explicit parameter:
  `rng: Optional[Union[np.random.Generator, int]] = None`.
- **Generator Preservation & Resolution**:
  If `isinstance(rng, np.random.Generator)`, the caller-provided generator is used directly, preserving its exact mutation state and sequence progression. If `rng` is an integer seed or `None`, it is converted via:
  ```python
  local_rng = rng if isinstance(rng, np.random.Generator) else np.random.default_rng(rng)
  ```
- **Prohibited**: Never call `np.random.seed()`, `random.seed()`, or manipulate global RNG state.
- **Parallel Workers**: When delegating stochastic work across processes via `_parallel.py`, parent seeds must be spawned into child seeds using `np.random.SeedSequence(seed).spawn(n_jobs)` to guarantee deterministic reproducibility across worker counts.

#### 2. Device Convention
- Functions supporting hardware acceleration accept:
  `device: str = "cpu"` (with valid options `"cpu"`, `"cuda"`).
- Resolution occurs through `jnwb._backend.resolve_device(device, context=...)`.
- **Fallback Observability**: When `"cuda"` is requested but unavailable, the runtime falls back to CPU and **must emit a `RuntimeWarning`** via `jnwb._backend.warn_device_fallback(context, exc)`. Silent fallback without diagnostic warning is strictly prohibited.
- For structured analysis results where hardware acceleration was requested, the return object records the device actually used in a `device: str` attribute.

#### 3. Missing/Invalid Data vs Non-Identifiability
- **Invalid Input / Misuse**: Nonsensical dimensions, negative frequencies, negative power values passed into logarithmic transforms, incompatible array shapes, or missing required metadata fail loudly by raising `ValueError` or `TypeError`.
- **Non-Identifiability**: When mathematically valid data fails to support an empirical fit (e.g. support score below threshold, diverging parameter optimization, zero variance across contacts), the function must **not raise an unhandled exception** and must **never return fabricated numbers or silently substitute fallbacks**. Instead, it returns an explicit structured state with `accepted=False`, boundary status flags, and `crossover_contact=None` or layer label `'na'`.

#### 4. Structured Return Types
- Complex multi-parameter estimators return dataclasses (e.g. `VFlipResult`, `AperiodicFitResult`, `DirectedResult`, `JRSAResult`).
- To preserve backwards compatibility with tuple/dictionary unpacking and ensure serializability, structured return objects implement `.to_dict()` and standard mapping access (`__getitem__`).

#### 5. Axis & Dimension Vocabulary
- Array dimensions follow standard named tensor shapes:
  - Continuous signals: `(n_times, n_channels)`
  - Trial-aligned epochs: `(n_trials, n_channels, n_times)`
  - Time-frequency representations: `(n_trials, n_channels, n_freqs, n_times)` or `(n_channels, n_freqs, n_times)`
  - Spectral profiles: `(n_channels, n_freqs)`
- Axis arguments default to explicit keywords (e.g., `axis=-1`, `aggregate_over=0`).

#### 6. Physical Units
- Coordinates and electrode contact depths: **micrometers ($\mu\text{m}$)**.
- Sampling rates and spectral frequencies: **Hertz ($\text{Hz}$)**.
- Continuous time: **seconds ($\text{s}$)**.
- Peristimulus / raster windows and bin sizes: **milliseconds ($\text{ms}$)** when prefixed with `_ms` (e.g., `win_ms`, `bin_ms`, `tau_ms`).
- Power & Spectral Density: Preserves and derives input signal units rather than assuming microvolts. For an input signal in unit $U$ (e.g., $\text{V}$ or $\mu\text{V}$), raw spectral density is $(U)^2/\text{Hz}$ and integrated band power is $(U)^2$. When input units are unrecorded or generic arrays are processed, dimensional quantities are $(U_{\text{in}})^2/\text{Hz}$ and $(U_{\text{in}})^2$. Conversion to decibels ($\text{dB}$) is dimensionless ratio-scale relative to baseline, explicitly controlled via `to_db` or `aggregate_to_db` and computed last.

#### 7. Estimand Disambiguation: Population Trajectory PCA
- `PopulationAnalyzer.population_trajectory(X)`: Unstandardized covariance PCA (centering only, $\mathbf{X} - \boldsymbol{\mu}$). Features with higher firing rates dominate variance.
- `compute_population_trajectory(session, ...)`: Standardized correlation PCA (z-score scaling, $(\mathbf{X} - \boldsymbol{\mu})/\boldsymbol{\sigma}$). Units contribute equally regardless of baseline rate.
- Both estimators represent valid, mathematically distinct estimands. They are documented with their specific standardization policy and must not be conflated or silently substituted.

#### 8. Synthetic Data Policy (`testing.synth`)
- Synthetic generators and null fixtures belong in `jnwb/testing/` (e.g. `jnwb/testing/synth.py`).
- Synthetic generators are designated solely as verification and test infrastructure, never presented as empirical observations.

---

### 9.2 Planned Operation Specifications (0.2.1 through 0.2.3)

| Operation | Module Location | Input & Shapes | Units | Estimator & Math | Output / Result Type | Failure & Non-Identifiability | Randomness & Device | Composition & Tests |
|---|---|---|---|---|---|---|---|---|
| `aperiodic_fit` | `jnwb.spectral` | `freqs`: `(n_freqs,)`, `psd`: `(n_freqs,)` or `(..., n_freqs)`, `freq_range: Tuple[float, float]`, `mode: str = "fixed"` | $\text{Hz}$, $(U_{\text{in}})^2/\text{Hz}$ | Fits $L(f) = b - \log_{10}(k + f^\chi)$ in log-log space. Fixed mode sets $k=0$; knee mode optimizes $k > 0$. Does not recompute PSD. | `AperiodicFitResult` dataclass with `offset`, `exponent`, `knee`, `r_squared`, `freq_range`, `mode`, `accepted`. | Raises `ValueError` for non-positive freqs/psd or $<4$ points. Returns `accepted=False` if optimization fails to converge. | Deterministic (no RNG). Runs on CPU. | Composes with `compute_psd` and `welch_psd`. Tested against analytic power-law spectra. |
| `relative_power` | `jnwb.spectral` | `power`: `(...)`, `baseline`: `(...)`, `model: str = "mean_of_ratios"` | $(U_{\text{in}})^2$ or $(U_{\text{in}})^2/\text{Hz}$ (ratio is dimensionless or $\text{dB}$) | Ratio of power to baseline. Explicit `model` selection: `"mean_of_ratios"` ($\mathbb{E}[P/P_0]$), `"ratio_of_means"` ($\mathbb{E}[P]/\mathbb{E}[P_0]$), or `"log_ratio"` ($10 \log_{10}(P/P_0)$). | `np.ndarray` matching broadcast shape. | Raises `ValueError` for negative or non-finite inputs, zero baseline division, or unrecognized model. | Deterministic. CPU/CUDA via `resolve_device`. | Composes with `band_power` and `aggregate_to_db`. Tested for distinct numerical results across models. |
| Session-level exact stats | `jnwb.statistics` (`StatisticalAnalysis`) | `exact_sign_flip(diffs)`, `mann_whitney_p_floor(n1, n2)`, `clopper_pearson(k, n, alpha)`, `fdr_correct(p_values)` | Unitless p-values / proportions | Exact permutations ($2^N$ sign flips), combinatorial p-value floor ($\binom{n_1+n_2}{n_1}^{-1}$), exact binomial inversion, and Benjamini-Hochberg FDR. | Exact p-values, confidence interval tuples, or adjusted array. | Raises `ValueError` for $N=0$ or invalid probability inputs. Handles ties conservatively. | Exact combinatorial (no RNG required for $N \le 20$; Monte Carlo for $N > 20$ with `rng`). | Composes with group comparison tests. Tested against full enumeration. |
| `stream_npz_array` | `jnwb.io` | `file_path: Path`, `key: str`, `slice_tuple: Tuple[slice, ...]` | Array dtype | Streams memory-mapped or chunked slices from compressed/uncompressed NPZ archives without full-file RAM allocation. | `np.ndarray` slice | Raises `KeyError` if key missing; raises `ValueError` for corrupt archives or unsupported compression layouts. | Deterministic. IO bound. | Verified by comparing memory consumption and array equality against `np.load`. |
| `probe_geometry` | `jnwb.addressing` | NWB `ElectrodesTable` or coordinate arrays `coords`: `(n_channels, 3)`, `units: str = "um"` | $\mu\text{m}$ | Extracts contact spacing, linear ordering, and probe layout. Validates inter-contact pitch within tolerance without assuming anatomical identity. | `ProbeGeometry` dataclass with `contact_positions`, `nominal_pitch`, `is_linear`, `orientation`. | Raises `ValueError` for ambiguous/duplicate coordinates or unsupported units. | Deterministic. CPU only. | Composes with NWB electrode tables and laminar profiling. |
| `vflip` | `jnwb.laminar` | `psd`: `(n_channels, n_freqs)`, `freqs`: `(n_freqs,)`, `band_low: Tuple`, `band_high: Tuple` | $\mu\text{m}$, $\text{Hz}$ | Computes the frequency layer inversion profile from min-max relative power per frequency across contacts, differencing the two band depth profiles after each is rescaled to $[0, 1]$; evaluates the bin-count-normalized support score $\Omega$ against a calibrated threshold. | `VFlipResult` dataclass with `crossover_contact`, `support_score`, `accepted`, `profile`. | Non-interactive. Rejection when $\Omega < \Omega_{\text{thresh}}$ returns `accepted=False` and `crossover_contact=None`. | Deterministic. CPU/CUDA. | Composes with `probe_geometry` and PSD arrays. Tested on inverted and non-motif spectra. |
| `vflip_from_lfp` | `jnwb.laminar` | `lfp`: `(n_channels, n_times)`, `fs: float`, `band_low: Tuple`, `band_high: Tuple` | Input voltage $U_{\text{in}}$, $\text{Hz}$ | Strict composition: `compute_psd(lfp, fs) -> vflip(psd, freqs)`. | `VFlipResult` | Propagates PSD and vflip validation errors. | Deterministic. CPU/CUDA. | Tested for exact numerical identity against manual composition. |
| `label_layers` | `jnwb.laminar` | `vflip_result: VFlipResult`, `probe_geom: ProbeGeometry` | Categorical labels | Assigns superficial, input, and deep cortical layer labels relative to verified crossover contact. | `Dict[int, str]` mapping channel index to layer label (`"deep"`, `"input"`, `"superficial"`, or `"na"`). | If `vflip_result.accepted` is `False`, all channels receive `'na'`. Never guesses or imputes layers on failed fit. | Deterministic. CPU only. | Composes with `vflip` and `probe_geometry`. |
| `testing.synth` | `jnwb.testing.synth` | `n_channels: int`, `n_times: int`, `fs: float`, motif parameters | $\mu\text{V}$, $\text{s}$ | Generates synthetic signals (laminar crossover motifs, AR noise, pink/white noise, shared common response). | `np.ndarray` | Raises `ValueError` for non-positive dimensions or invalid parameters. | Fully controlled via `rng: Optional[Union[Generator, int]]`. | Used across test suites to verify calibration, false positive rates, and recovery. |
| `xflip` | `jnwb.laminar` | `corr_matrix`: `(n_channels, n_channels)` or raw arrays, `method: str = "pearson"` | Correlation coefficient | Evaluates contiguous cross-channel correlation blocks; tests boundary significance against autocorrelation-preserving surrogates. | `XFlipResult` dataclass with `block_bounds`, `p_values`, `accepted`. | Raises `ValueError` for non-square or ill-conditioned matrices. Rejection returns `accepted=False`. | Surrogate generation controlled via `rng`. | Composes with `channel_correlation_matrix`. Tested against block models and white noise. |
| `zflip` | `jnwb.laminar` | `cross_spec`: `(n_channels, n_channels, n_freqs)` or complex TFR | Coherency | Evaluates phase-gradient asymmetry and imaginary coherency across lamina, reducing sensitivity to zero-phase-lag coupling. | `ZFlipResult` dataclass with `phase_gradient`, `wpli_profile`, `accepted`. | Raises `ValueError` for zero imaginary coherency or ill-conditioned cross-spectra. | Controlled via `rng` when permutation is used. | Composes with `imaginary_coherency` and `wpli`. |


