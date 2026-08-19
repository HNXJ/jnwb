# jnwb / repo test evidence — PRGS Prepare snapshot, 2026-08-15

All commands run directly in this session, from the repo root (`C:\workspace\omission`), on
the `dev` working tree as it stood at the time (see `PRGS_PREPARE.md` for the exact
commit/status). Interpreter: `.venv/Scripts/python.exe` (Python 3.14.3, project's own venv —
**not** the system `C:\Python314\python.exe` that `pytest`/`python` resolve to on PATH by
default; using the wrong interpreter would likely fail on missing `pynwb`/`hdmf`/etc.).

## Command 1 — whitespace/diff sanity

```
git diff --check
```
**Exit code: 0** (no output shown as an error — the tool surfaced trailing-whitespace notices
for `context/figures/...fig05_band_power_hierarchy.py` and the regenerated `fig03.svg`, which
`git diff --check` reports but does not fail the exit code on for this ruleset). **Proves:**
no unresolved merge-conflict markers, no encoding errors that would break a naive diff/patch
apply. **Does not prove:** anything about code correctness or content.

## Command 2 — collection

```
.venv/Scripts/python.exe -m pytest -q --collect-only
```
**442 tests collected, 0 collection errors**, 5.74s. **Proves:** every test file under `tests/`
imports cleanly against the current `jnwb` package (no broken import graph, no syntax errors in
test files or their transitive imports). **Does not prove:** the tests exercise real behavior —
collection success is necessary, not sufficient.

## Command 3 — full run

```
.venv/Scripts/python.exe -m pytest -q
```
**Result: 2 failed, 396 passed, 44 skipped, 2074 warnings, 156.12s.**

### Failures (both in `tests/test_skill_tree_consolidation.py`)

```
FAILED tests/test_skill_tree_consolidation.py::TestSingleCanonicalSkillTree::test_claude_skills_dir_exists_and_nonempty
  AssertionError: expected at least 10 skills, found 7:
  ['labyrinth','manuscript','omission-data','omission-figures','omission-signal',
   'omission-spiking','omission-statistics']

FAILED tests/test_skill_tree_consolidation.py::TestSingleCanonicalSkillTree::test_claude_skills_are_git_tracked
  AssertionError: .claude\skills\jnwb-core\SKILL.md exists but is not git-tracked
```

**OBSERVED FACT, with a receipt, not an inference:** these two tests assert a **pre-2026-08-12**
skill-tree shape — ≥10 skills including a `jnwb-core` skill. Commit `47d364e`
("harness: one-time Claude harness reset -- 18 skills to 9, retire competing constitutions",
currently `HEAD`) deliberately consolidated 18 skills → 9 (`omission-data, omission-signal,
omission-spiking, omission-statistics, omission-figures, manuscript, labyrinth` project-scoped +
`numerical-computing, biophysical-modeling` user-scoped — the 7 the test found is exactly the
project-scoped subset) and moved the 14 retired project skills (including `jnwb-core`) to
`context/archive/harness-reset-20260812/`. **This test was never updated for that change.** It
is not testing a real regression; it is asserting a doctrine the project itself intentionally
reversed. This is a textbook instance of the harness-audit category "a rule that is no longer
enforced by the implementation" — except inverted: here the *test* still enforces the *old*
rule, and the *implementation* (the harness reset commit) is what changed. See
`HARNESS_AUDIT.md` for the disposition recommendation.

**Everything else passed or was explicitly skipped** (44 skips — not independently triaged this
pass; `pytest -q -rs` was not run to enumerate skip reasons, flagged as an unresolved gap below).

**Warnings:** 2074 total, overwhelmingly `sklearn`'s `SVC(probability=True)` deprecation
(2010 instances from `test_cv_grouping_acceptance.py` alone, 64 from `test_fig04_leakage_safe.py`)
— a library deprecation notice, not a project bug.

## What passing tests actually prove (and don't)

442 tests is a real number, but per CLAUDE.md's own doctrine ("Executing without error is not
verification of content") and this task's explicit instruction ("Do not interpret 'tests pass'
as proof of scientific correctness"), the pass count alone establishes only: the code paths
exercised by these 442 tests run to completion on their given (mostly synthetic-fixture) inputs
without raising and without an assertion failure. It does **not** establish:

- that the *right* invariant is being tested (a test can assert stale/wrong behavior and still
  "pass" against itself — no instance of this was found this pass, but it wasn't ruled out
  either, beyond the one skill-tree case above which is the *inverse* problem);
- that real-NWB-data code paths behave the same as their synthetic-fixture counterparts (see
  below — most of the 442 tests are synthetic-fixture, not real-data, by design per the
  2026-08-12 harness-reset commit's own stated principle, "Truth sources are executable, not
  remembered" — `scripts/test_discover_corpus.py`'s 14 tests are explicitly synthetic-fixture,
  by the reset commit's own description);
- coverage completeness — several load-bearing modules have no dedicated test file at all
  (`jnwb/omission_identity.py`, 699 lines including two quarantined-but-live decoding
  functions, has **no** `test_omission_identity.py`; `jnwb/ontology.py` has no
  `test_ontology.py`, only indirect coverage via `test_factories.py`).

## Real-data vs synthetic/mock test distinction

**Not fully resolved this pass** — the task instructions ask to "distinguish explicitly" real
NWB fixtures/smoke tests from synthetic/mock ones. What is confirmed:

- `scripts/test_discover_corpus.py` (14 tests, referenced in the 2026-08-12 reset commit
  message) is **explicitly synthetic-fixture** by that commit's own description, "including a
  guard that fails if frozen paths or subject ids reappear in the source" — i.e. it is
  *designed* to never touch real data or real paths.
- `tests/test_jnwb_nwb_integration.py` (filename suggests real-NWB integration) exists but was
  **not opened this pass** to confirm whether it reads a real `.nwb` file from `D:/nwb/omission`
  or a synthetic fixture. **This is an open item, not a claimed finding** — see
  `NEXT_ACTIONS.md`.
- Given `context/PROJECT_STATE.md`'s own corpus-readiness table shows real NWB data exists and
  is reachable on this machine (22/22 `nwb_ok`, dated 2026-08-12), a real-data smoke test is at
  minimum *possible* in this environment; whether `pytest -q` as run above touched any real NWB
  file was not instrumented (no `D:\nwb\omission` file-access logging was captured).

## Not run this pass

- `pytest -q -rs` (skip-reason enumeration) — 44 skips not triaged individually.
- Any jnwb-specific integration/smoke script outside the `tests/` directory that might exercise
  real NWB fixtures end-to-end (e.g. a `scripts/` smoke-test entry point, if one exists —
  not searched for specifically).
- Coverage/line-coverage measurement — no `pytest --cov` run, so "coverage gap" statements
  above are structural (no test file with a matching name) not measured (no line-coverage tool
  run).

## Summary verdict

**Receipt-backed claim:** `git diff --check` exit 0; 442 tests collect; 396 pass, 2 fail (both
attributable to one stale test asserting pre-reset harness shape, not a code regression), 44
skip (untriaged). **Inference:** the two failures are cosmetic/doctrine-drift, not
scientific-correctness regressions — moderate confidence, since the failing assertions are
about `.claude/skills/` shape, entirely orthogonal to `jnwb`'s scientific code paths.
**Unresolved:** real-data vs. synthetic-fixture split across the 442 tests is not enumerated;
skip reasons are not enumerated; no coverage measurement exists.
