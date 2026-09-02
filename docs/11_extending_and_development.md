# 11. Extending `jnwb` & Developer Guide

This document is the canonical developer authority for maintaining, extending, and testing `jnwb` without degrading the released package or violating scientific invariants.

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
- **Warning-Free Builds**: The Sphinx documentation suite must compile with zero warnings under `-W`:
  ```bash
  python -m sphinx -W -b html docs docs/_build/html
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
├── skills/        # reusable agent procedures
├── scripts/       # deterministic repository tooling
├── artifacts/     # non-root work products + AGENTS.md reference
└── root           # frozen package/repository control surface
```

### Permitted Root Entries (Allowlist)
- **Source & Tests**: `jnwb/`, `tests/`, `examples/`, `docs/`, `skills/`, `scripts/`, `omission/` (native example project)
- **Configuration & Metadata**: `pyproject.toml`, `README.md`, `CHANGELOG.md`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `.readthedocs.yaml`
- **CI / VCS**: `.git/`, `.github/`
- **Repository Artifact Container**: `artifacts/`

### `artifacts/` Policy
The `artifacts/` directory is the canonical location for non-package, repository-associated artifacts that should not occupy root:

```text
artifacts/
├── AGENTS.md        # Generalized agent reliability policy reference artifact
├── benchmarks/      # Performance profiles, timing benchmarks, scalability receipts
├── reports/         # Analysis reports, verification audits, coverage summaries
├── figures/         # Intermediate visual review renders, diagnostic figures
├── receipts/        # Hash logs, test receipts, data provenance records
└── scratch/         # Disposable developer scripts, temporary test data
```

- **Rule**: Temporary scripts, test data, and ad-hoc exports must be placed in `artifacts/scratch/` or ignored via `.gitignore`, never committed to root.
- **Agent Policy Reference**: For contributors and automated systems seeking the generalized, reusable agent work policy, epistemic taxonomy (`observed` | `derived` | `inferred` | `assumed` | `unknown`), and execution grammar ($W = P(RG)^N S$), see `artifacts/AGENTS.md`.

---

## 7. Core Scientific Invariants

All contributors and automated agents must adhere to the 7 scientific invariants:

1. **Signal Class Independence**: SUA/SPK, MUA, and LFP represent physically distinct observables. Never pool features across modalities without explicit namespace tags.
2. **Estimand Disambiguation**: Clearly distinguish between prevalence, magnitude, decodable information, and biophysical mechanism.
3. **Causal & Directional Verbs**: $\text{Association} \ne \text{Directionality} \ne \text{Causality}$. Metrics like Granger causality or phase slope index measure temporal predictive asymmetry, not physical perturbation causality.
4. **Logarithm Last**: For spectral power estimation, average raw power across trials first, normalize by baseline, and compute $10 \cdot \log_{10}(\text{power})$ once at the final step.
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
7. Sphinx -W     Verify warning-free documentation compilation.
       │
8. Harness Gate  Execute python scripts/harness_gate.py.
       │
9. Seal & Push   Verify git status, stage exact paths, and push to dev branch.
```
