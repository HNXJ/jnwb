# Blocker fixpoint receipt, 0.2.14

| Field | Value |
|---|---|
| commit | `4aaaae6103d3b046dde0023ca7d8d470a82bf611` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows |
| pass | Independent reviewers, none of whom wrote what they reviewed: two closure passes over `v0.2.13..b2a3e85a` (Muse, read-only; Haiku 5.5 at xhigh, with probes), a Muse review of the repairs `b2a3e85a..8be01dcc`, then Sonnet 5.5 reviews of `8be01dcc..47f060c4` and `47f060c4..4aaaae61` |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass (Muse, read-only) over `v0.2.13..b2a3e85a`: about 109 `[0.2.14]` changelog lines, 23 added symbols against `__all__` and `docs/api.md`, 4 removed names, 20 signatures read against their definitions, the raise sites of the announced refusals, G-04 over the 15 deferred items | `b2a3e85a` | PASS; refusal behaviour read in code, not run | 0 |
| Closure pass (Haiku 5.5, xhigh) over the same delta: 109 changelog bullets, 59 named symbols, 162 `docs/api.md` rows against `inspect.signature`, 226 `__all__` names against 226 rows, 88 runtime probes (27 announced refusals raised as stated), G-04 over the 15 deferred items | `b2a3e85a` | DEFECT claimed on two rows: (1) a 0-d array indexed with `...` was said to return the scalar; it returns a 0-d array, as NumPy does, so only the wording was wrong; (2) five `docs/api.md` annotations read `typing.Collection` or `typing.Sequence` without `[str]`, as in 0.2.13. Both repaired in `56d021c3` | 0 after repair |
| Haiku G-04 notes: `AmbiguousMappingError` and `UndeclaredUnitError` were described as if raised; README, `docs/architecture.md` and the connectivity skill state guarantees that items 17-03, 17-07 and 17-08 extend | `b2a3e85a` | the two errors' changelog line now says no function raises them (`docs/errors.md` already did); the three claims are the deferred items' own subjects, tracked in the `# 0.2.15` todo section | 0 |
| Muse review of the repairs `b2a3e85a..8be01dcc`: the 0-d return path, no raise of the two reserved errors, the generator branch and its four rows, the roadmap and todo split, the changelog, the forward note | `8be01dcc` | PASS; the dispatcher measured the two items the reviewer could not: the longest `[0.2.14]` line is 120 characters, and 4 `docs/api.md` rows changed | 0 |
| Sonnet 5.5 review of `8be01dcc..47f060c4`: gate 19 drops the `is_lazy` field Python 3.15 adds to `Import` and `ImportFrom` while it is false (the 3.15 CI leg failed on three frozen bodies with local imports); item 17-61 and the rulings of 2026-10-27 | `47f060c4` | PASS; the dispatcher measured the two items the reviewer inferred: gate 19 reports 0 violations on 3.12, 3.14 and 3.15 with the registered hashes unchanged, and the new test fails on the old code | 0 |
| Sonnet 5.5 review of `47f060c4..4aaaae61`: the release run of the first `v0.2.14` tag (40580823631) failed one test on CI's detached, branchless tag checkout, which expected at least 3 generated state rows where only the worktree and defect-class rows exist; the bound is now 2. The rest of the range is the 0.2.15 todo rows | `4aaaae61` | PASS; `generated_rows()` returns at least 2 rows on any checkout, and no other test or script assumes a local branch. The dispatcher measured the failure and the fix in a depth-1 detached clone of the tag: the test failed before and passes after, and `tests/test_state_reconstruction.py` passes there (22 passed, 1 skipped) | 0 |
| Dispatcher: the 0.2.7 block removed from `CHANGELOG.md` occurs once, verbatim, in `artifacts/archive/changelog_0.1.0-0.2.9.md` | `a22f2014` | PASS | 0 |

`b2a3e85a..8be01dcc` also returns roadmap rows 15-11, 16-12 and 12-21 from the todo stack (the dashboard lists deferred validation from tagged roadmap rows), regenerates the curation calibration receipt and the figure registry under 0.2.14, and rewrites the expired forward note on the three removed constructors as history.

## Receipts at `8be01dcc`

| Check | Result |
|---|---|
| Harness gates | 22 of 22 passed |
| Full suite | 10177 passed, 80 skipped, 38 xfailed, 0 failed (`jnwb_suite.sh`, stamp equal to the commit); 10178 passed at `4553b1da`, at `5d9e5749` and at `bdd6f456` |
| Docs build | strict MkDocs build passed |
| Peak-memory record | `jnwb_version` 0.2.14, measured at `a22f2014`; no operation grew past 20% and 5 MiB |
| Release gate | not yet run; it follows this receipt |
| NOT RUN | the CUDA constant-channel test |
