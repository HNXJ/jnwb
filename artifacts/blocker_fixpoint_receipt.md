# Blocker fixpoint receipt, 0.2.11

| Field | Value |
|---|---|
| commit | `b7b1ea7a0693c466fc44c99123c0f9a4a51683d5` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; next-cycle observations become `deferred-0.2.12` entries |
| pass | Independent reviewers, none of whom wrote what they reviewed: a closure critic (Opus) over `v0.2.10..64bc140d`, and a verifier (Opus) over the repair of what it found and the release delta to the commit above |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure critic over `v0.2.10..64bc140d` (188 files): every changelog fragment probed old against new; the four unit measures against AllenInstitute `ecephys_spike_sorting` at `919992748a53` on 3000 random units (worst relative difference 4.1e-15); tutorial 10's unit identity; the `align_mode` deprecation; `save_and_seal`; the unit-mismatch refusal; the deferrals of 11-07, 10-10, 11-06, 09-04, 11-32 and 12-13 against the Deferred predicate | `64bc140d` | DEFECT: `plot_wavemap` reused a cluster's color from the eighth cluster on, so two clusters merged in a static export | repaired in `2fcfb5f5`; five next-cycle findings are roadmap 12-15 |
| Verifier over the repair and `64bc140d..2fcfb5f5` in `jnwb/`: distinct colors for 1 to 24 clusters and non-contiguous labels, panels A and B agree, 25 clusters refused, no duplicate color within a palette, the new tests fail on the parent (5 failed) and pass at the commit (15 passed), the rest of the delta is the version bump | `2fcfb5f5` | PASS | 0 |

`2fcfb5f5..b7b1ea7a` changes no code: `index` 417 -> 428 and `install` 901 -> 912 words in the
length table, as `tests/test_documentation_form.py` measures them, one 12-14 bullet reworded, and
the `wavemap` extra's floor raised from `umap-learn>=0.5` to `>=0.5.6`, the oldest release with a
wheel, which `release_gate.py` STEP 0c requires.

## Receipts at `2fcfb5f5`

| Check | Result |
|---|---|
| Harness gates | 22 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| Full suite | runs on the commit that records this receipt, before the push; its summary is in that push's message |
| Peak-memory record | `jnwb_version` 0.2.11, measured on a clean tree at `13f64787`; later commits change `jnwb/vis/wavemap.py`, which no measured operation calls, tests, the changelog and the stacks |
| NOT RUN | `release_gate.py` STEPs 0 to 8 (network and build), the dependency-floors install (STEP 0c), the CUDA constant-channel test, CI on the commit that records this receipt |
