# Contributing to jnwb

Everything you need to make a change and get it merged: the mechanics first, then the
rules a change is held to. The working rules for agents and the repository map live in
[`AGENTS.md`](AGENTS.md). The contracts a *caller* can rely on -- randomness, devices,
shapes, units, and what each operation does when it cannot support a fit -- are
documentation, in
[`docs/10_operation_specifications.md`](docs/10_operation_specifications.md).

## Setup

Python 3.12 or newer. CI runs every declared version on both Ubuntu and Windows — six legs, and
`pyproject.toml` is where the declared set lives — so a change must work across the whole range,
not only at its ends.

```bash
git clone git@github.com:HNXJ/jnwb.git
cd jnwb
python -m venv .venv
.venv/Scripts/activate        # Windows;  source .venv/bin/activate  elsewhere
pip install -e ".[test,docs]"
```

Optional extras: `mcp` (the MCP server), `torch` and `gpu` (CuPy) for the accelerated
paths, `all` for everything. The GPU paths fall back to CPU with a warning when their
dependency is absent, so you can work on most of the library without them.

Verify the install:

```bash
python -m pytest tests/ -q
```

Run `python -m pytest tests/ -q` before pushing; all tests should pass on your interpreter.
CI exercises every version `pyproject.toml` declares, so a version the package claims is a
version CI runs. A small number of tests skip when optional extras are not installed.

## Branches

`dev` is where work lands. `main` holds releases and is fast-forwarded to `dev` when one
is cut — no merge commits, so the two never diverge.

Branch from `dev`, and open the pull request against `dev`. Push directly to `dev` only for
work you have run the full checks on. Never force-push either branch.

## Before you push

Three checks, in this order. All three run in CI, so running them locally only saves you a
round trip.

```bash
python -m pytest tests/ -q
python scripts/harness_gate.py
python scripts/docs_build.py
```

- **The suite** — every test, on the interpreter you ran. Run it on 3.12 as well if your
  change touches anything version-sensitive.
- **`harness_gate.py`** — 14 repository gates: the project boundary, skills, paths, the
  root allowlist, docs, the public API set, version agreement, the Python policy, import
  shadowing, project identifiers in code, NWB onboarding alignment, and repository-process
  vocabulary in `docs/`. It fails on structure, not behaviour.
- **`python scripts/docs_build.py`** — strict MkDocs via the same interpreter as pytest.
  Read the Docs sets `fail_on_warning`, so a warning here is a failed publish.

A fourth check exists and is **not** part of this sequence:

```bash
python scripts/release_gate.py
```

- **`release_gate.py`** — builds the wheel, installs it in a clean venv, and smoke-tests
  the installed package. It catches packaging mistakes (a module missing from the wheel, a
  broken extra) that the suite cannot see. Run it before tagging, not before pushing: it needs
  network access to build an environment, and no CI job executes it — the workflow imports
  `forbidden_entries` from it to check the built artifacts and never calls its `main`.

Stage exact paths. `git add .` sweeps in build output and scratch files.

## What goes in a change

- **Smallest change that reaches the acceptance you defined.** No drive-by edits.
- **A test for every fix.** A corrected bug gets a regression test that fails without the
  fix — see [Testing rule](#testing-rule) below for the probe classes expected.
- **Docs and skills in lockstep.** Changing a public symbol means updating `docs/` and
  `skills/` in the same commit.
- **A `CHANGELOG.md` entry** for anything a user would notice. Breaking changes say what
  breaks and how to keep the old behaviour.
- **A citation** for a published method, in the docstring and in `docs/references.md`,
  with a DOI you resolved rather than one you recalled.

## Extension rule

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

## Code rules and quality standards

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

## Public API rule

The top-level `jnwb` namespace is intentionally curated.

$$\text{New Public Symbol} \iff \text{Implementation} + \text{Tests} + \text{Documentation} + \text{Skill Routing}$$

- **Internal vs. Public**: Helper functions, intermediate utilities, and implementation details must remain private (prefixed with `_`) and un-exported in `__all__`.
- **No Inventions**: Never document or export unverified symbols.
- **Breaking Changes**: Breaking changes to public signatures require an explicit deprecation cycle with informative `DeprecationWarning` or `FutureWarning` notices before removal.

## Testing rule

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

## Documentation rule

- **Truth Precedence**: Code and direct empirical receipts define implemented behavior. Documentation must describe actual behavior without claiming stronger scientific capabilities than what is implemented and verified.
- **Lockstep Updates**: Any modification to a public symbol must update both the relevant documentation guide (`docs/`) and repository skill (`skills/`) in the same commit.
- **Warning-Free Builds**: The documentation must compile with zero warnings:
  ```bash
  python scripts/docs_build.py
  ```

## Repository root freeze and `artifacts/` policy

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

## Core scientific invariants

Every contributor adheres to these scientific invariants:

1. **Signal Class Independence**: SUA/SPK, MUA, and LFP represent physically distinct observables. Never pool features across modalities without explicit namespace tags.
2. **Estimand Disambiguation**: Clearly distinguish between prevalence, magnitude, decodable information, and biophysical mechanism.
3. **Causal & Directional Verbs**: $\text{Association} \ne \text{Directionality} \ne \text{Causality}$. Metrics like Granger causality or phase slope index measure temporal predictive asymmetry, not physical perturbation causality.
4. **Logarithmic Estimand Clarity**: Explicitly distinguish arithmetic mean of raw power ($\mathbb{E}[P]$, physical power conservation) from mean of logarithmic/decibel power ($\mathbb{E}[\log P]$, geometric mean / log-normal central tendency). Do not conflate the two estimands or treat raw-power averaging as an unconditional universal requirement without declaring the estimand.
5. **Unit of Inference**: Always declare whether statistical degrees of freedom reside at the unit, channel, trial, or session level.
6. **Valid Nulls**: A valid null is an empirical finding. Never alter test windows or parameters to artificially force statistical significance.
7. **No Synthetic Science**: Never present synthetic or dummy data as real electrophysiological observations.
8. **Scientific Vocabulary & Methodological Distinctions**: Prefer direct, compact, quantitative scientific terminology (`result`, `test`, `analysis`, `table`, `figure`, `method`, `limit`, `condition`) over process/governance jargon. Preserve critical distinctions: response magnitude does not imply temporal precision; detecting an effect does not by itself establish precise timing or an admissible latency; distinguish measurement precision, latency, estimator disagreement, and boundary censoring; descriptive lower-level percentages do not substitute for hypothesis tests at the declared higher-level inferential unit; association or directionality metrics do not establish physical causality.

## Standard development flow

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

## Where the work is queued

[`artifacts/todo_stack.md`](artifacts/todo_stack.md) holds the remaining work, grouped by
the version that will carry it, most consequential first. It holds only what is not yet
done — a finished item is deleted, because git and the changelog already record it. If you
finish something, delete it from the stack in the same commit.

## Releasing

Maintainers only, and only from a clean `dev` with the three pre-push checks green and
`release_gate.py` green as well — tagging is the point at which it stops being optional.

1. Bump the version in `pyproject.toml` and `jnwb/__init__.py`; write the `CHANGELOG.md`
   entry.
2. Commit to `dev`, push, and wait for CI to pass on that exact commit.
3. Fast-forward `main` to `dev` and push it.
4. Tag `vX.Y.Z` and push the tag. The tag push runs CI (test + build) only — it does **not**
   upload to PyPI.
5. Create a **GitHub Release** for that tag (non-prerelease). The workflow's `publish-pypi`
   job runs on `release: published` and uploads to production PyPI via trusted publishing.
6. Verify the result from PyPI in a fresh venv, rather than trusting the workflow's green
   tick. PyPI versions are immutable: a bad upload can never be replaced, only superseded.

**TestPyPI:** push an `rc` tag (`vX.Y.ZrcN`) or publish a GitHub Release marked prerelease;
either path runs the `publish-testpypi` job. `workflow_dispatch` with target `testpypi` is
also available for maintainers.

## Reporting a problem

Open an issue with the jnwb version, the interpreter, the platform, and the smallest script
that reproduces it. If it involves an NWB file, say what is unusual about the file — jnwb
carries repairs for malformed ones, and which repair applies matters.
