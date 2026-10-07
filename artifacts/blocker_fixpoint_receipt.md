# Blocker fixpoint receipt, 0.2.10

| Field | Value |
|---|---|
| commit | `f0bcf8d1a1b39075681f6d1c88d8847a7ef06b0a` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; next-cycle observations become `deferred-0.2.11` entries |
| pass | Independent reviewers, none of whom wrote what they reviewed: a closure critic (Opus) over the 0.2.10 changes at `3c91fe29`, a verifier (Sonnet) over the repair of what it found, and a re-verification critic (Opus) over the delta to the commit above |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure critic over `f2008fa4..3c91fe29`: 25 changelog bullets probed, 84 function bodies mapped, gates, publication order, deleted paths | `3c91fe29` | DEFECT: the changelog omitted the addressing and compression changes of PR #25; item 11-02 listed repaired problems; every item carried `deferred-0.2.10`; the `validate_nwb` dependency layers had no receipt | 3 repaired, 1 evidence receipt added |
| Verifier over the repair `c99263f8..5ad7017a`: each new bullet probed old against new, mutants on each repaired problem, the relabel, the evidence file | `5ad7017a` | FAIL on two checks: the top-level soft-link refusal was stated too broadly; P-312 and P-348 were stale | repaired in `0dc7514b` |
| Re-verification critic over `3c91fe29..f0bcf8d1`: the diff read in full, an AST diff of function bodies against `6502d2d7`, 14 old-against-new probes, the stack, STEP 0a, the wheel-leg guard, the evidence file | `f0bcf8d1` | PASS | 0 |

## Receipts at `f0bcf8d1`

| Check | Result |
|---|---|
| Full suite, `-n 12` | 7118 passed, 31 skipped, 20 xfailed, 0 failed |
| Harness gates | 22 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| `release_gate.py` STEP 0a | stops only on this receipt being absent |
| Peak-memory record | `jnwb_version` 0.2.10, measured on a clean tree at `3c91fe29`; later commits change tests, docs, the changelog and the todo stack |
| `validate_nwb` layers | `nwbinspector` 0.7.2 and `dandi` 0.81.0 exercised once in a throwaway environment (`artifacts/evidence/0.2.10/validate_nwb_layers.md`); the declared floors `nwbinspector>=0.6` and `dandi>=0.70` are not tested |
| NOT RUN | `release_gate.py` STEPs 0 to 8 (network and build), the dependency-floors install (STEP 0c), the CUDA constant-channel test, CI on the commit that records this receipt |
