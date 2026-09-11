# AGENTS.md — working rules for `jnwb`

Start here. §0 maps the repository, §2 holds the remaining work and §3 is the loop that
works through it; the rest says how to work here. `CLAUDE.md` carries phase and policy. A
project that *uses* jnwb keeps its own rules in its own repository.

**Leave no process-authorship narrative in the library surface.** Harness vocabulary
(agents, assistants, orchestration tooling) is named only in four places: `skills/`, this
file, one line in `README.md`, and `CONTRIBUTING.md`. Not in `jnwb/`, `tests/`, `scripts/`,
`docs/`, `CHANGELOG.md`, or code comments/docstrings — except **machine-required literals**
such as the path `agents/openai.yaml` in skill-structure tests, and standard technical
metadata in generated assets (e.g. Creative Commons RDF `cc:Agent` creator tags in Matplotlib
SVG output). `CLAUDE.md` is a tripwire supplement, not a fifth naming location. A reader of
the library should see a library.

## 0. Where things are

| Path | What you get there |
|---|---|
| `jnwb/__init__.py` | The public API: `__all__` is the authoritative symbol list |
| `jnwb/` | Library source. `_backend.py` decides CPU/GPU, `_parallel.py` runs `n_jobs` loops |
| `tests/` | The suite. Run it before and after a change (§6) |
| `scripts/harness_gate.py` | Repository gates 1–12 (§6) |
| `scripts/release_gate.py` | Builds the wheel, installs it in a clean venv, smoke-tests it |
| `skills/` | Task skills, one folder per area (§7). Load one before the work it covers |
| `artifacts/agents/` | Subagent definitions: `claim-verifier` re-derives one reported number from its receipt, `code-auditor` inventories a module against house standards, `sweep-runner` runs one shard of a sweep. Your host loads agents from its own directory (Claude Code: `.claude/agents/`), so copy them there to use them |
| `artifacts/todo_stack.md` | Remaining work, grouped by the version that carries it (§2). Finished items are deleted |
| `artifacts/fact_stack.md` | Small, human-authorized durable facts (§2). No pending actions; agents read but do not edit without explicit authorization |
| `artifacts/benchmarks/` | Performance baseline and import profile. `python scripts/benchmark_import.py --write` regenerates the profile |
| `docs/` | User docs, built by MkDocs. `api.md` lists every public symbol; `common_mistakes.md` lists the failure modes jnwb guards against |
| `docs/references.md` | Published sources for each method, with resolved DOIs; docstrings cite the same entries |
| `docs/11_extending_and_development.md` | How to add or change a function without breaking the release |
| `examples/quickstart_jnwb.py` | Smallest end-to-end script |
| `examples/notebooks/` | Notebooks on synthetic data; `tests/test_notebooks.py` executes every one |
| `pyproject.toml` | Version source, dependencies, Python floor |
| `CHANGELOG.md` | What changed per release, including breaking changes |
| `.github/workflows/workflow.yml` | CI: tests on 3.12 and 3.14 (Ubuntu, Windows), build, docs. Tag push validates only; production PyPI on GitHub Release `published`; `rc`/prerelease → TestPyPI |

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

## 2. The todo stack

One file holds the remaining work: `artifacts/todo_stack.md` (`docs/todo_stack.md` in a
repository with no `artifacts/`). Group by the version that will carry the item:

```markdown
# i.j.k
- do this
- test this
- if X: do Y; else: do Z

# i.j.(k+1)
- ...
```

**It contains only work not yet done.** A finished item is deleted, not ticked or moved to
a "closed" section. Git, the changelog and the receipts hold the history and the evidence;
duplicating them here makes a second record that goes stale on its own.

## 3. Loop

`W = P (R G)^N S`

- **Prepare** — read authorities, `artifacts/fact_stack.md`, `artifacts/todo_stack.md`, and
  current evidence; order the remaining work; define acceptance. A fact is not proof that
  mutable repository state currently satisfies it. If evidence contradicts a fact, surface
  the conflict and request review — do not silently rewrite the fact or the evidence.
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
   comment/docstring neutrality; see the non-blocking scan item in the todo stack).
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

## 5. Vocabulary

- Association, directionality, and causality are three claims. Granger and phase slope
  index measure temporal-lag asymmetry, not anatomy.
- Prevalence ("how many units respond") is a different question from magnitude,
  decodability, and mechanism. Answering one does not answer another.
- Spikes and LFP are distinct observables. Do not pool across them without namespacing.

## 6. Tools

| Command | Asserts | A pass means |
|---|---|---|
| `python -m pytest tests/ -q` | The full suite | Every test passed on the interpreter you ran |
| `python scripts/harness_gate.py` | Gates 1–12, in order | Boundary, skills, paths, root, docs, API set, versions, Python policy, import shadowing, forbidden study tokens in Gate 6 scan surface |
| `python scripts/release_gate.py` | Release readiness | Run before tagging |
| `mkdocs build --strict` | Docs build | RTD sets `fail_on_warning`, so a warning here is a failed publish |

Supported interpreters are declared in `pyproject.toml` and enforced by Gate 8. CI tests
the floor and the newest declared version.

## 7. Skills

Load the skill before doing the work rather than reinventing its contents.

| Skill | Covers |
|---|---|
| `jnwb` | Router, safeguards, entry point |
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
  one is possible.
- No secrets in the repository, context, or transcripts. If one is exposed, stop, say so,
  and recommend rotation.

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

# Spikes: PSTH (times in s, window in ms), causal smoothing, onset fit
t_ms, rate, sem = jnwb.raster_psth(spike_times, event_onsets, win_ms=(-200.0, 500.0), bin_ms=10.0)
smooth = jnwb.causal_exp_smooth(rate, bin_ms=10.0, tau_ms=25.0)
fit = jnwb.fit_exponential_onset(t_ms, smooth, t0_bounds=(0.0, 250.0))   # dict

# LFP: complex TFR (mask edges with tfr.coi_mask), band power, decibels last
tfr = jnwb.complex_tfr(lfp, fs=1000.0, freqs=np.linspace(10, 40, 4))
beta_raw = jnwb.band_power(
    lfp, fs=1000.0, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False,
)
baseline_raw = jnwb.band_power(
    baseline_lfp, fs=1000.0, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False,
)
db = jnwb.aggregate_to_db(beta_raw, baseline_raw, how="mean_of_ratios", aggregate_over=0)

# Bad channels from inter-channel correlation (channels x time)
bad, summary, z = jnwb.bad_channels_from_correlation(jnwb.channel_correlation_matrix(lfp_ch), z_thresh=5.0)

# Directed measures: both return DirectedResult; seed fixes the surrogates
te = jnwb.transfer_entropy(x, y, n_surrogates=200, seed=42)
psi = jnwb.phase_slope_index(x, y, fs=1000.0, bands=(15.0, 30.0))

# Statistics
res = jnwb.StatisticalAnalysis.exploratory_compare(g1, g2)   # parametric + bootstrap
q = jnwb.StatisticalAnalysis.fdr_correct(p_values)           # Benjamini-Hochberg
```

GPU: functions taking `device="cuda"` resolve it through `_backend.resolve_device` and warn
when they fall back to CPU. Parallel: `n_jobs` (default 1) goes through
`_parallel.parallel_map`; `n_jobs=-1` uses every core.
