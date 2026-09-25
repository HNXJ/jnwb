# Blocker fixpoint receipt, 0.2.6.1

| Field | Value |
|---|---|
| commit | `5cf625d43934c02ee7d5e2fe64b49150b929979d` |
| new release-blocking problems found | 0 |
| ruling | 2026-09-25: the 0.2.6.1 patch carries the silently wrong results and misleading documentation found in the shipped 0.2.6, and the three defects of the same kind its verifiers measured |
| pass | Independent verifiers, none of whom wrote what they verified, then one closure pass over `v0.2.6..b18c35d1`. Each verifier reproduced the defect at the commit before its repair, confirmed the repair with probes of its own design, and killed mutants of the repair after proving its selector passed on the unmutated tree |

## Verification

| Scope | Verified at | Verdict | Findings, then repaired and re-verified |
|---|---|---|---|
| `jrsa` circular-shift null for paired metrics | `eaebbaf9` | PASS; FPR 0.048 default against 0.530 iid on 400 independent AR(1) pairs; `iid` equals 0.2.6 in 76 cases | A test gap (axis-0 rotation survived) and the "aligned axis" wording: repaired in `935a1cb2` and `df33ee7c` |
| `jrsa` row-metric warning and paired-bootstrap refusal (ruled 2026-09-25) | `45525efb` | PASS; numbers byte-identical to 0.2.6 with `iid` | The `block_len` rule, a refusal test for `block`, the `adim` and `lag` docstrings: repaired in `df33ee7c` |
| Symbolic transfer entropy refused; directed estimators honour `rng` | `bc04a791` | PASS; int seeds byte-identical to 0.2.6 | A pre-existing few-trial surrogate defect, ruled and repaired as below |
| Directed surrogates circularly shift below 7 trials (ruled 2026-09-25) | `a3096b3b` | PASS; pooled FPR 0.045 to 0.053 at 3 to 6 trials; 1, 2, 7 and 12 trials byte-identical | A stale quickstart sentence (`b48f9ab0`) and a behaviour test at 4 to 6 trials (`4f92dff1`) |
| Documentation that invited wrong claims | `d18937f0` | PASS for the changes; four more wordings found | Repaired in `540fc074` and, for the Granger docstrings, `bc04a791` |
| Closure over `v0.2.6..b18c35d1`, extended to `3b646e4b` | `b18c35d1` | PASS | Every changelog claim re-measured; 87 of 102 int-seed cases bit-identical to 0.2.6 and the 15 others only in surrogate fields at 3 and 6 trials, as ruled |

`3b646e4b` compares two pinned floats to `rtol=1e-12` after CI's Linux legs differed in the last
bits; the closure pass reviewed it and found no platform dependence in the patch. `5cf625d4`
applies the pass's changelog precision correction and moves its observations to the todo stack.
Every finding that is not a blocker is a `deferred-0.2.7` entry in `artifacts/todo_stack.md`
(IB-39 to IB-55).

## Receipts

| Check | Result |
|---|---|
| Full suite at `b18c35d1` (closure pass) | 4887 passed, 6 skipped, 0 failed |
| Full suite at `b18c35d1` (dispatcher) | 4888 passed, 5 skipped, 0 failed |
| Harness gates | 19 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| Closure mutants | 6 of 7 killed; the survivor, a block null that keeps block order, is IB-53 |
| New release-blocking problems found | 0 |
