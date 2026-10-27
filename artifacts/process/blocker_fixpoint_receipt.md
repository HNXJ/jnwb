# Blocker fixpoint receipt, 0.2.14

| Field | Value |
|---|---|
| commit | `8be01dcc1d1572c4119161c8bf2b8041a61b8a57` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows |
| pass | Independent reviewers, none of whom wrote what they reviewed: two closure passes over `v0.2.13..b2a3e85a` (Muse, read-only; Haiku 5.5 at xhigh, with probes), then a Muse review of the repairs `b2a3e85a..8be01dcc` |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass (Muse, read-only) over `v0.2.13..b2a3e85a`: about 109 `[0.2.14]` changelog lines, 23 added symbols against `__all__` and `docs/api.md`, 4 removed names, 20 signatures read against their definitions, the raise sites of the announced refusals, G-04 over the 15 deferred items | `b2a3e85a` | PASS; refusal behaviour read in code, not run | 0 |
| Closure pass (Haiku 5.5, xhigh) over the same delta: 109 changelog bullets, 59 named symbols, 162 `docs/api.md` rows against `inspect.signature`, 226 `__all__` names against 226 rows, 88 runtime probes (27 announced refusals raised as stated), G-04 over the 15 deferred items | `b2a3e85a` | DEFECT claimed on two rows: (1) a 0-d array indexed with `...` was said to return the scalar; it returns a 0-d array, as NumPy does, so only the wording was wrong; (2) five `docs/api.md` annotations read `typing.Collection` or `typing.Sequence` without `[str]`, as in 0.2.13. Both repaired in `56d021c3` | 0 after repair |
| Haiku G-04 notes: `AmbiguousMappingError` and `UndeclaredUnitError` were described as if raised; README, `docs/architecture.md` and the connectivity skill state guarantees that items 17-03, 17-07 and 17-08 extend | `b2a3e85a` | the two errors' changelog line now says no function raises them (`docs/errors.md` already did); the three claims are the deferred items' own subjects, tracked in the `# 0.2.15` todo section | 0 |
| Muse review of the repairs `b2a3e85a..8be01dcc`: the 0-d return path, no raise of the two reserved errors, the generator branch and its four rows, the roadmap and todo split, the changelog, the forward note | `8be01dcc` | PASS; the dispatcher measured the two items the reviewer could not: the longest `[0.2.14]` line is 120 characters, and 4 `docs/api.md` rows changed | 0 |
| Dispatcher: the 0.2.7 block removed from `CHANGELOG.md` occurs once, verbatim, in `artifacts/archive/changelog_0.1.0-0.2.9.md` | `a22f2014` | PASS | 0 |

`b2a3e85a..8be01dcc` also returns roadmap rows 15-11, 16-12 and 12-21 from the todo stack (the dashboard lists deferred validation from tagged roadmap rows), regenerates the curation calibration receipt and the figure registry under 0.2.14, and rewrites the expired forward note on the three removed constructors as history.

## Receipts at `8be01dcc`

| Check | Result |
|---|---|
| Harness gates | 22 of 22 passed |
| Full suite | 10177 passed, 80 skipped, 38 xfailed, 0 failed (`jnwb_suite.sh`, stamp equal to the commit) |
| Docs build | strict MkDocs build passed |
| Peak-memory record | `jnwb_version` 0.2.14, measured at `a22f2014`; no operation grew past 20% and 5 MiB |
| Release gate | not yet run; it follows this receipt |
| NOT RUN | the CUDA constant-channel test |
