# Blocker fixpoint receipt, 0.2.15

| Field | Value |
|---|---|
| commit | `1b55385b2db160b0176e5ef00a687c5808a44e8a` |
| new release-blocking problems found | 0 |
| ruling | `AGENTS.md` section 11 condition 3: the terminating condition is an independent blocker-focused pass that finds no new release-blocking problem; G-04 (2026-10-19): each advertised scientific claim is checked against the deferred rows |
| pass | Independent reviewers, none of whom wrote what they reviewed: two closure passes over the repository at `6eeb3d04` (Sonnet 5.5, Gemini 3.8 flash through agy, read-only), the same two over the release delta `6eeb3d04..47812466`, then Sonnet 5.5 over the repairs `47812466..804ce1f3` and `804ce1f3..1b55385b` |

## Verification

| Scope | Verified at | Verdict | New blockers |
|---|---|---|---|
| Closure pass (Sonnet 5.5): the open stack holds no row; no `required-0.2.15` item; each roadmap row (15-11, 16-12, 12-21, 17-70) and deferred item (17-75 to 17-79) against README, `docs/`, the skills and the changelog fragments; the `signal_class` fragment against its three call sites | `6eeb3d04` | NO NEW BLOCKER; numeric claims in `docs/0*.md` and figure captions not checked | 0 |
| Closure pass (agy, read-only) over the same scope | `6eeb3d04` | NO NEW BLOCKER; `docs/06` and `jnwb/viz.py` limit right-open bins to `raster_psth`, so 17-70 contradicts no claim | 0 |
| Release delta (Sonnet 5.5): `[0.2.15]` lines opened against `jnwb/`, version surfaces, the 0.2.10 block moved to `artifacts/archive/changelog_0.1.0-0.2.9.md` (identical to the block at `6eeb3d04` apart from one trailing blank line), the calibration and peak-memory records | `47812466` | NO NEW BLOCKER; no `jnwb/` file but `__init__.py` changed after `6eeb3d04` | 0 |
| Release delta (agy): the same scope | `47812466` | two changelog defects: the `signal_class=` line named one file for three operations, and `nwb_read_io`'s refusal at call was missing; repaired in `804ce1f3`. A third claim, that the dropped Fixed entries for `sha256_groups` and `units_table` belong in the changelog, is not taken: neither function exists at `v0.2.14`, so no released behaviour changed | 0 after repair |
| Repair (Sonnet 5.5): `804ce1f3` changes only `CHANGELOG.md`; both lines read against `jnwb/_units.py:121`, its three call sites and `jnwb/nwb_io.py:340-346`; the third claim judged not a blocker | `804ce1f3` | NO NEW BLOCKER | 0 |
| Repair (Sonnet 5.5): the suite at `804ce1f3` failed two tests after the bump (2 failed, 10604 passed); `1b55385b` changes only the 35 `jnwb_version` fields of `scripts/figures/figure_registry.toml` and excuses `docs/02` line 304, a 0.2.14 removal, as history in `tests/test_prose_version_claims_are_live.py` | `1b55385b` | NO NEW BLOCKER | 0 |

## Receipts at `1b55385b`

| Check | Result |
|---|---|
| Harness gates | 22 of 22 passed |
| Full suite | 10606 passed, 81 skipped, 38 xfailed, 0 failed (`jnwb_suite.sh`, stamp equal to the commit); 10607 passed, 0 failed at `6eeb3d04` |
| CI on `dev` | `6eeb3d04`: CI/CD run 41270902410 and dashboard run 41270902245 concluded success; the run on the commit recording this receipt follows it |
| Curation calibration | rerun at the declared 0.2.15; 2784 trials, table unchanged from 0.2.14; estimator `5a8c30c542be7772` |
| Peak-memory record | `jnwb_version` 0.2.15, measured at `a6d4ddac`; every operation at or below 505.875 MiB |
| Frozen-validated | nine bodies changed by the 0.2.15 non-finite refusals re-verified at `896d6159`, each with a guard-removal mutant killed; gate 19 passes |
| Release gate | not yet run; it follows this receipt |
