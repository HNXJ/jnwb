# AGENTS.md — working rules for `jnwb`

The single operational contract for this repository. `CLAUDE.md` carries phase and policy;
this file carries how to work. A project that *uses* jnwb keeps its own rules in its own
repository.

## 1. Evidence

Every claim is one of `observed | derived | inferred | assumed | unknown`. Say which.

- `execution != verification`. Exit status 0 means the process ran.
- `configured != loaded != executed != verified`.
- `memory != current state`. Re-read the file; do not quote a path, count, or flag from
  recall.

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
   values are for visual constants or output marked synthetic.
2. **Take the logarithm last.** Average raw power, divide by baseline, `10*log10` once.
   Averaging decibels biases each site by its own noisiness. Use `aggregate_to_db`.
3. **`jnwb/` imports nothing from a project folder.** The dependency runs one way. jnwb
   must behave identically whether a project package is installed or absent. Enforced by
   `tests/test_jnwb_frozen_boundary.py`.
4. **Units, coordinate frames, sample rates, and 0- vs 1-indexing do not change silently**
   across a jnwb function boundary. State intentional breaks at the change site.
5. **Nulls are explicit.** Label permutation requires a named exchangeability scheme.
   Anything consuming randomness takes an `rng` and reports what it used.
6. **Device and worker count never change a number.** `n_jobs` is a speed knob; a result
   computed on GPU records that it was.

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
| `python scripts/harness_gate.py` | Gates 1–11, in order | Boundary, skills, paths, root, docs, API set, versions, Python policy, import shadowing |
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

Agent definitions live in `artifacts/agents/` and are tracked. The root holds no `.claude/`.

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
