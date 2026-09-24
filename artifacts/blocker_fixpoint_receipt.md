# Blocker fixpoint receipt, 0.2.6

| Field | Value |
|---|---|
| commit | `6c65151145e58048cc66dc43fb1f5bc0f837fe33` |
| new release-blocking problems found | 0 |
| ruling | 2026-09-23, closure at `1d5e8b81`: the fourteen blockers that pass found are repaired and each repair is verified independently with a kill; that targeted verification replaces a further open-ended pass, and only a regression from the repairs blocks |
| pass | Independent verifiers, none of whom wrote what they verified. Each reproduced the defect at the commit before its repair, confirmed the repair with probes of its own design, and killed a mutant of the repair after proving its selector passed on the unmutated tree |

## Verification

| Scope | Verified at | Verdict | Regressions found, then repaired and re-verified |
|---|---|---|---|
| B5 `channel_conversion`, B6 `starting_time`, B7 linked timestamps, B14 STEP 0a reads HEAD | `c0e551d7` | PASS; one regression | The B7 link scan was quadratic: linear scan `518b9fd2`, PASS at `c7949748` |
| B8 `zflip` orientation, B9 TE formula, B10 jrsa directions, B11 `sliding`, B12 TE `k`, B13 PCA sign ties; the frozen-validated register, all six entries re-killed by the verifier's own mutants | `d42abd9c` | PASS | none |
| B1 permutation ties, B2 empty TFR cells, B3 unit-invariant sign flip, B4 constant traces | `d42abd9c` | PASS for B3 and B4; two regressions | An offset inflated the B1 tolerance and the B2 `mean` setter kept NaN: centring `5d081256` and setter `9504ebee`, which opened a reload-order regression and weakened the identity fixture; repaired in `873d5472` and `6c651511`, PASS at `6c651511` |
| Follow-ups: linear link scan, `starting_time` in README and common_mistakes, constant-channel NaN in `wpli`, `imaginary_coherency` and `zflip` (ruled 2026-09-24) | `c7949748` | PASS | none |

Every finding that is not a regression from these repairs is a `deferred-0.2.7` entry in `artifacts/todo_stack.md` (P-332 to P-351). The too-small p-values of other permutation nulls (P-345) lead the 0.2.7 work.

## Receipts at `6c651511`

| Check | Result |
|---|---|
| Full suite | 4829 passed, 1 failed: `test_vis.py::test_canvas_save_and_seal_triple_export` with "Couldn't close or kill browser subprocess", the known kaleido flake; `tests/test_vis.py` alone: 17 passed |
| Harness gates | 19 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| Final verifier | 7 of 7 mutants killed; new release-blocking problems found: 0 |
