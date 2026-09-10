# AGENTS.md — working rules for `jnwb`

Start here. §0 maps the repository; the rest says how to work in it. `CLAUDE.md` carries
phase and policy. A project that *uses* jnwb keeps its own rules in its own repository.

## 0. Where things are

| Path | What you get there |
|---|---|
| `jnwb/__init__.py` | The public API: `__all__` is the authoritative symbol list |
| `jnwb/` | Library source. `_backend.py` decides CPU/GPU, `_parallel.py` runs `n_jobs` loops |
| `tests/` | The suite. Run it before and after a change (§5) |
| `scripts/harness_gate.py` | Repository gates 1–12 (§5) |
| `scripts/release_gate.py` | Builds the wheel, installs it in a clean venv, smoke-tests it |
| `skills/` | Task skills, one folder per area (§6). Load one before the work it covers |
| `artifacts/agents/` | Subagent definitions: `claim-verifier` re-derives one reported number from its receipt, `code-auditor` inventories a module against house standards, `sweep-runner` runs one shard of a sweep. Your host loads agents from its own directory (Claude Code: `.claude/agents/`), so copy them there to use them |
| `artifacts/benchmarks/` | Performance baseline and import profile |
| `docs/` | User docs, built by MkDocs. `api.md` lists every public symbol; `common_mistakes.md` lists the failure modes jnwb guards against |
| `docs/11_extending_and_development.md` | How to add or change a function without breaking the release |
| `examples/quickstart_jnwb.py` | Smallest end-to-end script |
| `pyproject.toml` | Version source, dependencies, Python floor |
| `CHANGELOG.md` | What changed per release, including breaking changes |
| `.github/workflows/workflow.yml` | CI: tests on 3.12 and 3.14 (Ubuntu, Windows), build, docs. A `v*` tag push publishes to PyPI; an `rc` tag goes to TestPyPI |

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

## 2. Loop

`W = P (R G)^N S`

- **Prepare** — reconstruct goal, evidence, constraints, tools; define acceptance.
- **Review** — observe before changing; find the highest-value justified change.
- **Progress** — apply the smallest authorised change; preserve invariants; test.
- **Seal** — verify acceptance, reconcile artifacts, leave a recoverable handoff.

Review yields: acceptance met → Seal · justified action → Progress · missing evidence
or authority → stop and ask.

## 3. Invariants this library protects

1. **No empirical value in any output that no script computed from data.** Hardcoded
   values are for visual constants or output marked synthetic. Missing data fails loudly.
2. **Take the logarithm last.** Average raw power, divide by baseline, `10*log10` once.
   Averaging decibels biases each site by its own noisiness. Use `aggregate_to_db`.
3. **`jnwb/` imports nothing from a project folder.** The dependency runs one way. jnwb
   must behave identically whether a project package is installed or absent. Enforced by
   `tests/test_jnwb_frozen_boundary.py`. Condition codes, session labels, area vocabularies
   and findings stay out of `jnwb/`, `docs/`, `skills/` and `tests/` (Gate 6 scans for them).
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

## 4. Vocabulary

- Association, directionality, and causality are three claims. Granger and phase slope
  index measure temporal-lag asymmetry, not anatomy.
- Prevalence ("how many units respond") is a different question from magnitude,
  decodability, and mechanism. Answering one does not answer another.
- Spikes and LFP are distinct observables. Do not pool across them without namespacing.

## 5. Tools

| Command | Asserts | A pass means |
|---|---|---|
| `python -m pytest tests/ -q` | The full suite | Every test passed on the interpreter you ran |
| `python scripts/harness_gate.py` | Gates 1–12, in order | Boundary, skills, paths, root, docs, API set, versions, Python policy, import shadowing, project identifiers in code |
| `python scripts/release_gate.py` | Release readiness | Run before tagging |
| `mkdocs build --strict` | Docs build | RTD sets `fail_on_warning`, so a warning here is a failed publish |

Supported interpreters are declared in `pyproject.toml` and enforced by Gate 8. CI tests
the floor and the newest declared version.

## 6. Skills

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

## 7. Changes

- Smallest change that reaches the acceptance you defined. No drive-by edits.
- Stage exact paths. Never `git add .` or `-A`.
- Confirm branch and upstream before commit, push, or rebase. Read the target before
  deleting or overwriting.
- Preserve originals; write revisions as new files.
- Commit or push only when asked.
- A public API change is announced in `CHANGELOG.md` and carries a deprecation path where
  one is possible.
- No secrets in the repository, context, or transcripts. If one is exposed, stop, say so,
  and recommend rotation.

## 8. Writing

Cut adjective stacks, negation ("X is not Y"), restated obviousness, repeated caveats, and
hedged claims that should be deletions. If something is unverified, remove it rather than
labelling it. Say "policy" or "rule", never "doctrine" or "governance". Lead with the
result.

## 9. Recipes

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
beta = jnwb.band_power(lfp, fs=1000.0, freq_range=jnwb.CANONICAL_BANDS["beta"])
db = jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=0)

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
