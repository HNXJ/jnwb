# Blocker fixpoint receipt, 0.2.7

| Field | Value |
|---|---|
| commit | `66766b2a42ebcd6e79f0de5d5ff09b59cf04f782` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` §11 condition 3, amended 2026-09-23: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; next-cycle observations become `deferred-0.2.8` entries |
| pass | Independent critics, none of whom wrote what they reviewed: a closure pass over every deferral and the changes since v0.2.6, then a delta review of each change that landed after it |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass: every `deferred-0.2.8` entry attacked with one question (could it make evidence used to qualify 0.2.7 falsely pass), a blocker sweep of `v0.2.6..b9943452`, the 0.2.7 required sections, and a run of each release-gate step | `b9943452` | PASS; two stale deferral reasons (P-227, P-307) restated from the pass's receipts | 0 |
| `zflip` per-pair surrogate test and the no-surrogate ruling, reviewed in two rounds with the critic's own constructions (8 contacts, lag 1, a zero-lag-correlated end contact) | `32bb77c9` | PASS; false accepts 0 to 1 in 100 against a level of 2/51 | 0 |
| Plotly export tests on one bounded session browser, reviewed in two rounds, with a browser killed mid-session | `e5477a5c` | PASS | 0 |
| The version bump to 0.2.7, the CHANGELOG heading, the version-derived test literals and the benchmark records, reviewed by the integrator against the diff | `66766b2a` | PASS | 0 |

## Receipts at `66766b2a`

| Check | Result |
|---|---|
| Full suite, `-n 12` | 5766 passed, 9 skipped, 0 failed |
| Harness gates | 21 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| Peak-memory record | `jnwb_version` 0.2.7, measured on a clean tree at `7246934f` |
| dev ruleset | the admin bypass removed on 2026-09-29; `bypass_actors` reads back empty and the deletion and non-fast-forward rules stay |
