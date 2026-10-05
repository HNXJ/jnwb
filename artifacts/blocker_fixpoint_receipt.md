# Blocker fixpoint receipt, 0.2.9

| Field | Value |
|---|---|
| commit | `9205437867f0ea11477eedeb61e983f4b6db73c0` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` §11 condition 3, amended 2026-09-23: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; next-cycle observations become `deferred-0.2.10` entries |
| pass | Independent reviewers, none of whom wrote what they reviewed: a closure critic over the 0.2.9 changes, then a verifier over the release delta, then a re-verification of its repair |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure critic (Opus) over `v0.2.8..2d852b0d`: public behaviour against the changelog fragments and `docs/api.md`, skills routing, the release and harness gates, the workflow's publication order and figure-font step, the unit-quality changes; second pass over every deferral | `2d852b0d` | No blocker; no deferral reclassified. Four next-cycle findings filed in 10-08, 10-09 and 10-15 (`artifacts/evidence/0.2.9/closure_pass_2026-10-05.md`) | 0 |
| Verifier (Opus) over `2d852b0d..56cfb935`: the version bump, the assembled CHANGELOG against `v0.2.8..HEAD -- jnwb/` with probed values, the peak-memory record, the relabel to `deferred-0.2.10` | `56cfb935` | One required: five surfaces still at 0.2.8 (`__release_date__`, `README.md`, `docs/agents.md`, the import profile) and 9 failing tests; one changelog wording slip. Repaired in `2f984b5d` | 0 after the repair |
| Re-verification of `56cfb935..92054378`: no remaining 0.2.8 claim, 09-16's CI evidence, full suite and gates | `92054378` | PASS | 0 |

## Receipts at `92054378`

| Check | Result |
|---|---|
| Full suite, `-n 12` | 6618 passed, 29 skipped, 0 failed |
| Harness gates | 22 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| `release_gate.py` | stops only on this receipt being absent |
| Peak-memory record | `jnwb_version` 0.2.9, measured on a clean tree at `75ec1f54`; only the record and the todo stack change after it |
| CI at `bd242873` | every unconditional job concluded success (run 37318301569); the figure comparison ran on the 3.12, 3.13 and 3.14 ubuntu legs and skipped only on the dependency-floors leg |
