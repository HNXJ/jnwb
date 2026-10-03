# Blocker fixpoint receipt, 0.2.8

| Field | Value |
|---|---|
| commit | `2e450b3c8d1d8353653762bc4c99856f254340be` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` §11 condition 3, amended 2026-09-23: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; next-cycle observations become `deferred-0.2.9` entries |
| pass | Independent reviewers, none of whom wrote what they reviewed: a closure critic over the library changes since v0.2.7, then a verifier over the closure repairs and the release record, then a delta verification of its repairs |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure critic (second model) over `v0.2.7..b6e1fa2f -- jnwb/`, each new function checked against its cited definition by hand computation | `b6e1fa2f` | Two required: a bare list of spike times split into one-spike units; `spike_count_correlation` cited as trial-based r_sc while it correlates time bins. Both repaired in `a404a9ee`, with exact-boundary bursts and the `compute_psd` default floor. Three deferred to 09-08 | 0 after the repair |
| Changelog completeness against `v0.2.7..HEAD -- jnwb/`, by the integrator | `a404a9ee` | Four new public functions, `compute_psd(nperseg=)` and the `directed_network` thread-count fix had no fragment; added | 0 after the repair |
| Verifier over `b6e1fa2f..0a44d402`: the closure repairs, the version bump, the CHANGELOG against the code, the benchmark records | `0a44d402` | One required: the bare-list check consumed a generator, giving 0 units. Repaired in `2ab9e031`, with the warm import benchmark (no bytecode cache was written) and the granger changelog bullet | 0 after the repair |
| Delta verification of `2ab9e031` and `2e450b3c` | `2e450b3c` | PASS: a generator gives the b6e1fa2f result, bare lists stay refused, the new case fails on a404a9ee; the warm row is a warm import; the granger bullet measured within its bound | 0 |
| A file-reading review through the agy worker was attempted four times and returned no answer each time; it contributes nothing to this receipt | n/a | not used | n/a |

## Receipts at `2e450b3c`

| Check | Result |
|---|---|
| Full suite, `-n 12` | 6186 passed, 29 skipped, 0 failed |
| Harness gates | 22 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| Peak-memory record | `jnwb_version` 0.2.8, measured on a clean tree at `2ab9e031` |
| CI at `0a44d402` | every unconditional job concluded success (run 37138319821) |
