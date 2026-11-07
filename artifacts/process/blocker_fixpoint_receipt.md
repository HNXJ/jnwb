# Blocker fixpoint receipt, 0.2.16

| Field | Value |
|---|---|
| commit | `cb781455f37076c74624933ea95248cdfb0116f3` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows |
| pass | Independent reviewers, none of whom wrote what they reviewed: two closure passes over the repository at `7d11325b` (Sonnet 5.5; Muse Spark 1.3 through opencode, read-only, no shell), then Sonnet 5.5 over the repair `7d11325b..cb781455` |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass (Sonnet 5.5): `[0.2.16]` lines against `jnwb/`; added and removed public names (`git diff v0.2.15..HEAD -- jnwb/__init__.py`, `public_surface.json`) each with a changelog line; version surfaces; roadmap rows deferred past 0.2.16 (15-11, 12-21, 16-12, 17-130 to 17-141) and the 0.2.17 items against README, `docs/`, the skills and the changelog; the open stack holds no row; no `required-0.2.16` or `deferred-0.2.16` item | `7d11325b` | NO NEW BLOCKER | 0 |
| Closure pass (Muse, read-only) over the same scope | `7d11325b` | NO NEW BLOCKER; about 20 of the changelog lines opened, the rest by pattern; `git diff` and the suite not run (no shell) | 0 |
| Repair (Sonnet 5.5): the suite at `7d11325b` failed on three records the bump made stale; `cb781455` drops the released 0.2.16 row from `release_plan.json`, moves `[0.2.11]` to `artifacts/archive/changelog_0.1.0-0.2.9.md` (byte-identical block, 36 lines) and reruns the curation calibration at 0.2.16 (only version stamps change) | `cb781455` | NO NEW BLOCKER; 176 tests over the changelog, calibration and ontology readers passed | 0 |

## Receipts at `cb781455`

| Check | Result |
|---|---|
| Harness gates | 22 of 22 passed |
| Full suite | 10817 passed, 83 skipped, 38 xfailed, 0 failed (`jnwb_suite.sh`, stamp equal to the commit) |
| CI on `dev` | the run on the commit recording this receipt follows the push |
| Curation calibration | rerun at the declared 0.2.16; 2784 trials, table unchanged from 0.2.14; estimator `5a8c30c542be7772` |
| Peak-memory record | `jnwb_version` 0.2.16, recorded in `7d11325b`; every operation under 505.875 MiB |
| Frozen-validated | gate 19 passes |
| Release gate | not yet run; it follows this receipt |
