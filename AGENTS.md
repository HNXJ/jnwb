# AGENTS.md — working rules for `jnwb`

Start here. §0 maps the repository, §2 holds the remaining work and §3 is the loop that
works through it; the rest says how to work here. **This file is the only repository-level
instruction file.** There is no second rule set at the root and no per-assistant variant;
a rule that is not here is not a rule of this repository. A project that *uses* jnwb keeps
its own rules in its own repository.

**Leave no process-authorship narrative in the library surface.** Public documentation may
describe AI agents, skills, routing, and agent-assisted use when these are public jnwb
capabilities. Internal harness terminology, repository agent roles, implementation process,
and private coordination vocabulary must not leak into public documentation unless required
to explain a public interface.

Not in `jnwb/`, `tests/`, `scripts/`, `CHANGELOG.md`, or code comments/docstrings — except
**machine-required literals** such as the path `agents/openai.yaml` in skill-structure tests,
and standard technical metadata in generated assets (e.g. Creative Commons RDF `cc:Agent`
creator tags in Matplotlib SVG output). A reader of the library should see a library.

Amended 2026-09-19. The previous rule named `docs/` among the places harness vocabulary may
not appear, which contradicted an intentionally agent-usable package and was already broken
by four published pages. The boundary is now public capability against internal process, not
the word "agent".

## 0. Where things are

| Path | What you get there |
|---|---|
| `jnwb/__init__.py` | The public API: `__all__` is the authoritative symbol list |
| `jnwb/` | Library source. `_backend.py` decides CPU/GPU, `_parallel.py` runs `n_jobs` loops |
| `tests/` | The suite. Run it before and after a change (§6) |
| `scripts/harness_gate.py` | Repository gates 1–13 (§6) |
| `scripts/release_gate.py` | Builds the wheel, installs it in a clean venv, smoke-tests it |
| `skills/` | Task skills, one folder per area (§7). Load one before the work it covers |
| `artifacts/agents/` | Portable role definitions: `authority`, `critic`, `actor`, `verifier`, `docs-harness`, `jnwb-developer`. Decoupled from domain skills (`role` $\perp$ `domain`). Parameterized via delegation packets |
| `artifacts/todo_stack.md` | Remaining work, grouped by the version that carries it (§2). Finished items are deleted |
| `artifacts/fact_stack.md` | Small, human-authorized durable facts (§2). No pending actions; agents read but do not edit without explicit authorization |
| `artifacts/benchmarks/` | Performance baseline and import profile. `python scripts/benchmark_import.py --write` regenerates the profile |
| `docs/` | User docs, built by MkDocs. `api.md` lists every public symbol; `common_mistakes.md` lists the failure modes jnwb guards against |
| `docs/references.md` | Published sources for each method, with resolved DOIs; docstrings cite the same entries |
| `CONTRIBUTING.md` | How to add or change a function without breaking the release |
| `examples/quickstart_jnwb.py` | Smallest end-to-end script |
| `examples/notebooks/` | Notebooks on synthetic data; `tests/test_notebooks.py` executes every one |
| `pyproject.toml` | Version source, dependencies, Python floor |
| `CHANGELOG.md` | What changed per release, including breaking changes |
| `.github/workflows/workflow.yml` | CI: tests on 3.12, 3.13 and 3.14 (Ubuntu, Windows), build, docs. Tag push validates only; production PyPI on GitHub Release `published`; `rc`/prerelease → TestPyPI |

## 1. Evidence

Every claim is one of `observed | derived | inferred | assumed | unknown`. Say which.

- `execution != verification`. Exit status 0 means the process ran.
- `configured != loaded != executed != verified`.
- `memory != current state`. Re-read the file; do not quote a path, count, or flag from
  recall.
- A file that points at other files (this map, a skill index, a symbol list) can name
  something that no longer exists without erroring. Resolve entries against disk.
- Counts written in prose go stale. Re-run and read the output.

**No claim without a receipt.** "Done", "passes", "fixed" require the command and its
output in the same message. Otherwise say "ran X, got Y".

**Running without error does not verify content.** Before reporting a number, read the
code that produced it and confirm it traces to a computation on real data rather than a
literal, an RNG draw, or a fallback branch.

When sources conflict, authority runs: the receipt on disk, then live repository state,
then machine-readable state files, then prose. Unresolved conflict on a material point
stops the work and surfaces both sides.

## 2. The fact stack and todo stack

$$\texttt{fact\_stack} = \text{stable human-authorized facts}$$

$$\texttt{todo\_stack} = \text{mutable unresolved execution}$$

| File | Holds | Agents may edit? |
|---|---|---|
| `artifacts/fact_stack.md` | Durable project direction and invariants | No — challenge with evidence; surface conflicts to Hamm |
| `artifacts/todo_stack.md` | Remaining executable work, grouped by version | Yes — delete finished items; add only unresolved work |

(`docs/fact_stack.md` / `docs/todo_stack.md` when the repository has no `artifacts/`.)

The todo stack groups work by the version that will carry it:

```markdown
# i.j.k
- do this
- test this
- if X: do Y; else: do Z

# i.j.(k+1)
- ...
```

**The todo stack contains only work not yet done.** A finished item is deleted, not ticked or
moved to a "closed" section. Git, the changelog, and receipts hold history; duplicating
completed work here goes stale.

Current evidence can falsify whether a fact still applies; it does not authorize rewriting a
fact without Hamm.

## 3. Loop

`W = P (R G)^N S`

- **Prepare** — load, in order: (1) `AGENTS.md` (this file), (2) `artifacts/fact_stack.md`,
  (3) `artifacts/todo_stack.md`, (4) relevant skills (§7), (5) current repository evidence
  (re-read targets, run probes, collect receipts). Order the remaining work; define
  acceptance. A fact is not proof that mutable repository state currently satisfies it. If
  evidence contradicts a fact, surface the conflict to Hamm — do not silently rewrite the
  fact or the evidence.
- **Review** — review the last result; update the todo stack; choose the next item. Commit
  validated changes, push to `dev`, verify the branch is in sync.
- **Progress** — apply the smallest authorised change; preserve invariants; test; return to
  Review.
- **Seal** — verify the release is complete; remove the completed items from the stack;
  commit, push, verify a clean sync.

Keep running Review → Progress while useful work remains. Stop when a decision that is the
human's to make blocks everything left, or when authority or evidence is missing.

Do not stop after one item. Do not commit nothing. Do not leave validated changes
unpushed. Do not cross a version boundary before sealing it.

## 4. Invariants this library protects

1. **No empirical value in any output that no script computed from data.** Hardcoded
   values are for visual constants or output marked synthetic. Missing data fails loudly.
2. **Take the logarithm last.** Average raw power, divide by baseline, `10*log10` once.
   Averaging decibels biases each site by its own noisiness. Use `aggregate_to_db`.
3. **`jnwb/` imports nothing from a project folder.** The dependency runs one way. jnwb
   must behave identically whether a project package is installed or absent. Enforced by
   `tests/test_jnwb_frozen_boundary.py`. Condition codes, session labels, area vocabularies
   and findings stay out of `jnwb/`, `docs/`, `skills/` and `tests/` (Gate 6 scans a fixed
   forbidden-token list in `jnwb/`, `skills/`, and selected docs — not `tests/` or full
   comment/docstring neutrality).
   A corpus convention, such as two spellings of one area, is the project's to normalise;
   a request to encode one in jnwb is a reason to stop.
4. **Units, coordinate frames, sample rates, and 0- vs 1-indexing do not change silently**
   across a jnwb function boundary. State intentional breaks at the change site.
5. **Nulls are explicit.** Label permutation requires a named exchangeability scheme.
   Anything consuming randomness takes an `rng` (`np.random.default_rng(seed)`) and reports
   what it used. Never call `np.random.seed()`.
6. **Device and worker count never change a number.** `n_jobs` is a speed knob; a result
   computed on GPU records that it was.
7. **Call the library function instead of retyping its rule.** A retyped copy drifts from
   the docstring unnoticed. If the function's shape blocks reuse, widen the shape.
8. **Coupling magnitude, signed direction, delay estimation, and statistical inference are distinct claims.**
   Never infer propagation direction from unsigned coupling magnitude (e.g. wPLI >= 0). Never claim
   physical latency or conduction velocity without a verified linear unwrapped phase-frequency
   relation and predeclared identifiability criteria; report unavailable otherwise. Never claim
   "immunity" or "complete suppression" of volume conduction or reference contamination; describe
   as reducing sensitivity to zero-phase-lag coupling.

## 5. Vocabulary

- Association, directionality, and causality are three claims. Granger and phase slope
  index measure temporal-lag asymmetry, not anatomy.
- Prevalence ("how many units respond") is a different question from magnitude,
  decodability, and mechanism. Answering one does not answer another.
- Spikes and LFP are distinct observables. Do not pool across them without namespacing.
- wPLI, imaginary coherency, and phase slope index reduce sensitivity specifically to
  zero-phase-lag coupling; they do not confer immunity to volume conduction, non-zero-lag
  common inputs, source mixing, or reference-induced phase structure.
- Phase slope yields delay (Delta tau) only under a verified linear unwrapped phase-frequency
  relation; v = Delta z / Delta tau is an apparent phase-delay velocity under the fitted model,
  not unconditional propagation velocity.

## 6. Tools

| Command | Asserts | A pass means |
|---|---|---|
| `python -m pytest tests/ -q` | The full suite | Every test passed on the interpreter you ran |
| `python scripts/harness_gate.py` | Gates 1–13, in order | Boundary, skills, paths, root, docs, API set, versions, Python policy, import shadowing, forbidden study tokens in Gate 6 scan surface, NWB onboarding alignment |
| `python scripts/release_gate.py` | Release readiness | Run before tagging |
| `python scripts/docs_build.py` | Docs build (strict MkDocs via `sys.executable`) | RTD sets `fail_on_warning`, so a warning here is a failed publish. Do not call bare `mkdocs`; PATH may point at another interpreter. |

Supported interpreters are declared in `pyproject.toml` and enforced by Gate 8. CI tests
every declared version. Amended 2026-09-19: this said "the floor and the newest declared
version", which is the policy that let 0.2.5 ship a 3.13 classifier no CI leg exercised.

## 7. Skills

Load the skill before doing the work rather than reinventing its contents.

| Skill | Covers |
|---|---|
| `jnwb` | Router, safeguards, entry point |
| `jnwb-fact-action` | Execution control ($F \to R \to A \to V \to S$), authority loading order, independent verification |
| `jnwb-nwb-data` | NWB inspection, paths, metadata, electrodes, addressing |
| `jnwb-spiking` | Raster/PSTH, latency, causal smoothing, unit QC |
| `jnwb-lfp-spectral` | Filtering, TFR, band power, artifact repair |
| `jnwb-statistics` | Bootstrap, permutation, multiple comparisons, RNG |
| `jnwb-population` | Decoding, trajectories, jRSA, population geometry |
| `jnwb-connectivity` | Granger, PSI, transfer entropy |
| `jnwb-figures` | Visual QC, plotting, figure export |

## 8. Changes

- Smallest change that reaches the acceptance you defined. No drive-by edits.
- Stage exact paths. Never `git add .` or `-A`.
- Confirm branch and upstream before commit, push, or rebase. Read the target before
  deleting or overwriting.
- Preserve originals; write revisions as new files.
- Commit and push validated checkpoints on `dev` per §3; do not push to `main` or tag without
  explicit maintainer instruction.
- A public API change is announced in `CHANGELOG.md` and carries a deprecation path where
  one is possible, **and updates the routing rows in `skills/` in the same commit**. The
  rows hardcode signatures; nothing else keeps them true, and
  `tests/test_skills_validation.py` checks every row against `inspect.signature`, so a
  change that skips this fails the suite rather than shipping a row that calls the old
  signature.
- No secrets in the repository, context, or transcripts. If one is exposed, stop, say so,
  and recommend rotation.

### One writable agent per worktree

A repository worktree has exactly ONE writable agent. Parallel reviewers may read it;
parallel implementation agents require separate Git worktrees or branches.

This is not advisory. On 2026-09-15 two implementation agents ran against this worktree at
once, both auditing 0.2.4-04. One session's 26 zFLIP tests were written, run green, and then
overwritten by the other agent between the test run and the commit, so the commit that was
supposed to carry them contained only the source file. Nothing errored; the tests simply
ceased to exist, and the loss was found later by reading a reflog entry that named a commit
this session had not made.

The failure mode is that a shared worktree makes a clean `git status`, a passing test run,
and a successful commit all independently true and jointly meaningless. Recoverable history
does not make a shared worktree safe for concurrent writers.

Before editing a worktree you did not just create, confirm no other agent or process is
modifying it. If exclusive ownership cannot be established, STOP before editing. If you find
uncommitted changes you did not make, follow the single-writer recovery protocol in
`artifacts/todo_stack.md`: treat them as unowned evidence, never `stash`, `reset`, `restore`,
check out files, or reformat while they exist, and never `git add -A` across unresolved
ownership.

## 9. Writing

Cut adjective stacks, negation ("X is not Y"), restated obviousness, repeated caveats, and
hedged claims that should be deletions. If something is unverified, remove it rather than
labelling it. Say "policy" or "rule", never "doctrine" or "governance". Lead with the
result.

## 10. Recipes

Each call below runs as written on synthetic arrays. NWB loading and artifact repair are in
the `jnwb-nwb-data` and `jnwb-lfp-spectral` skills.

```python
import numpy as np
import jnwb

rng = np.random.default_rng(0)
fs = 1000.0

# Synthetic inputs, so every call below runs as written.
spike_times = np.sort(rng.uniform(0.0, 20.0, 4000))          # s
event_onsets = np.arange(1.0, 19.0, 0.5)                     # s
lfp = rng.normal(size=4000)                                  # one channel, n_times
baseline_lfp = rng.normal(size=4000)
lfp_trials = rng.normal(size=(20, 4000))                     # trials x time
baseline_trials = rng.normal(size=(20, 4000))
lfp_ch = rng.normal(size=(8, 4000))                          # channels x time
x, y = rng.normal(size=2000), rng.normal(size=2000)
g1, g2 = rng.normal(0.0, 1.0, 40), rng.normal(0.5, 1.0, 40)
p_values = rng.uniform(0.0, 1.0, 10)

# Spikes: PSTH (times in s, window in ms), causal smoothing, onset fit
t_ms, rate, sem = jnwb.raster_psth(spike_times, event_onsets, win_ms=(-200.0, 500.0), bin_ms=10.0)
smooth = jnwb.causal_exp_smooth(rate, bin_ms=10.0, tau_ms=25.0)
fit = jnwb.fit_exponential_onset(t_ms, smooth, t0_bounds_ms=(0.0, 250.0))   # dict
# fit['bound_status'] is None for an interior fit and 'lower'/'upper' when the optimiser
# stopped at a bound, where t0 is the bound rather than an estimate.

# LFP: complex TFR (mask edges with tfr.coi_mask), band power, decibels last
tfr = jnwb.complex_tfr(lfp, fs=fs, freqs=np.linspace(10, 40, 4))

# aggregate_to_db aggregates on the RATIO scale, so it needs the per-trial powers, not one
# number: band_power returns a float, and `aggregate_over=0` over a float raises AxisError.
beta_raw = np.array([
    jnwb.band_power(trial, fs=fs, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
    for trial in lfp_trials
])
baseline_raw = np.array([
    jnwb.band_power(trial, fs=fs, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
    for trial in baseline_trials
])
db = jnwb.aggregate_to_db(beta_raw, baseline_raw, how="mean_of_ratios", aggregate_over=0)

# Bad channels from inter-channel correlation (channels x time)
bad, summary, z = jnwb.bad_channels_from_correlation(jnwb.channel_correlation_matrix(lfp_ch), z_thresh=5.0)

# Directed measures: both return DirectedResult; rng fixes the surrogates
te = jnwb.transfer_entropy(x, y, n_surrogates=200, rng=42)
psi = jnwb.phase_slope_index(x, y, fs=fs, bands=(15.0, 30.0))

# Statistics
res = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2)   # parametric + bootstrap
q = jnwb.StatisticalAnalysis.fdr_correct(p_values)           # Benjamini-Hochberg
```

GPU: functions taking `device="cuda"` resolve it through `_backend.resolve_device` and warn
when they fall back to CPU. Parallel: `n_jobs` (default 1) goes through
`_parallel.parallel_map`; `n_jobs=-1` uses every core.
