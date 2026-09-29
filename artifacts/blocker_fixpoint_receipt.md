# Blocker fixpoint receipt, 0.2.7

| Field | Value |
|---|---|
| commit | `cb972c4888ffc40ba92365442cb46c5cb9c0d782` |
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
| The release gate's archive check at `1c68dfc6` refused the sdist, which the isolated build had given `AGENTS.md` although `MANIFEST.in` never included it: an explicit `exclude AGENTS.md`, and the manifest test now requires it and refuses any directive that adds the file back | `0c288f1b` | PASS: the rebuilt sdist holds no `AGENTS.md` | 0; the defect is repaired before release, and nothing released shipped it |
| An independent visual check of every docs figure, in both themes and at displayed size, found three that could cause wrong use: fig01 named a geometric depth class a cortical layer, fig04 drew a power-law fit over a spectrum it was not fitted to, and fig09 gave the phase slope index a rad/Hz unit. The figures, their captions and three figure-form tests are repaired, and the remaining quality findings are deferred to 0.2.8 | `cb972c48` | PASS | 0 after the repair |

## Receipts at `cb972c48`

| Check | Result |
|---|---|
| Full suite, `-n 12` | 5769 passed, 9 skipped, 0 failed |
| Harness gates | 21 PASS, 0 FAIL, 0 NOT RUN, 0 ERROR |
| Peak-memory record | `jnwb_version` 0.2.7, measured on a clean tree at `7246934f` |
| CI at `1c68dfc6` | every test leg and the distribution build passed |
| dev ruleset | the admin bypass removed on 2026-09-29; `bypass_actors` reads back empty and the deletion and non-fast-forward rules stay |
