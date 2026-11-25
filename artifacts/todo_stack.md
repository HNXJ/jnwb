# 0.2.17

Work order, roles, gates and owner questions toward the release candidate: `artifacts/process/release_checklist.md` (sections 4 and 9). The items below hold the defects and Checks; the checklist never restates a Check.


Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.16
closed on 2026-11-08 (tag `v0.2.16`, `0aa220ba`; tag CI/CD run 42513450995 success, TestPyPI and PyPI
verified, GitHub release body checked by `release_gate.py` STEP 0d). Items run fastest first.

Thinning and matching from the 2026-11-02 audits, each named by SHA: seven models at `7ca5b9a6` (17-83 to 17-105) and eight auditors at `9fd2b4bd` (P-216 rows, 17-128, 17-129). Lanes form at 0.2.16's close; 17-79 (which rewrote `_xflip.py`
and `_zflip.py`) landed at e6baac97. Each item applies the jarness standards: `match-cleanup` for
removals, `match-code-style` for code, `match-writing-style` for prose, `match-visual-style` for figures.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet (`artifacts/agents/jnwb-developer.md`); a lane is one linked worktree (`scripts/verify_lane.py` refuses a clone) and one worker; up to three lanes at once; a lane's items run in the order listed | lanes share no file, so they merge without conflict |
| A public signature, an estimand or a skill line goes to Hamm before code, batched in one message per wave; Haiku implements a ruled signature and never chooses one | public API and skills are Hamm's |
| A packet reproduces its bullet first, writes the failing test, then the fix; a `reviewer` that did not write it verifies; the integrator commits, owns the stacks, `CHANGELOG.md` and `docs/api.md` | the actor is never the verifier |
| Wave barrier: `python scripts/harness_gate.py`, the full suite, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then one bullet:
`ID: defect with numbers. Check: a predicate naming the file and the asserted value.`
At most eight lines per item.

### 17-144 The jaxfne isi_cv commits

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: 17-144-src (open stack). Provenance UNKNOWN, not verified absent (2026-11-25): absent in this machine's clones and bundle tips, in the Windows user tree (13 repositories readable; `C:/Windows`, `AppData/Local/Temp`, the recycle bin and system volume information not read), in `/mnt/h,i,k` to depth 6 only, and on `main-vmac` (its checked scope); origin has none. `E:/cl-jnwb16e` is absent from every `/mnt` drive.
Writes: `artifacts/benchmarks/realdata/isi_cv_recompute.py`, `artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json`, `artifacts/benchmarks/realdata/build_isi_cv_fixture.py`, `tests/fixtures/isi_cv_realdata_subsample.json`, `tests/test_isi_cv_realdata.py`.
- 17-144: three 16-12 commits on `E:/cl-jnwb16e` (0e06993c, 9980f58d, 5fa63dd3) for jaxfne-orchestrator.
  Observed 2026-11-12: path missing; SHAs absent from this clone and `origin`. Check: each on `dev` in that
  order, suite passes, jaxfne-orchestrator told.

### 17-99 One home per invariant across rule and doc files

Release: deferred-0.2.17.
Role: jnwb-developer. Skill: none. Blocked by: none for the spikes-and-LFP rule. `tests/test_spikes_lfp_restatements.py` checks each sentence that uses a pooling word against the canonical fact row (S16, owner ruling 2026-11-25): it requires the prohibition and rejects a permission or an exception. It does not read a sentence that states the rule without a pooling word (for example "combine" or "merge"). The four-outcomes and Python-matrix duplicates below still need an owner ruling for their check; shared `README.md`.
Writes: `.github/CONTRIBUTING.md`, `docs/architecture.md`, `README.md`, `docs/index.md`, `docs/glossary.md`, `artifacts/agents.md`.
- 17-99: `CONTRIBUTING.md:368-380` and `docs/architecture.md:128-171` restate the invariants AGENTS.md §4 keeps in the fact stack; the spikes-and-LFP rule ("never pool") is in 17 tracked files (`git grep -il 'never pool'`) and no fact row; "four outcomes" in three of the Writes files; the Python matrix on four pages. Check: each fact has one home and the others link to it.

### 17-166 Interval-table fallback duplicated in two modules

Release: deferred-0.2.18 (found by the 17-165 reviewer, 2026-11-24; does not block 0.2.17; relabelled 2026-11-25, the 0.2.17 gate counts deferred-0.2.17 as required).
Role: jnwb-developer. Skill: none. Blocked by: none. Lane: new `_temp_` lane from `dev`.
Writes: `jnwb/nwb_events.py`, `jnwb/nwb_inspect.py`.
- 17-166: the `("trials", "epochs", "invalid_times")` attribute fallback is written twice, `_interval_tables` in `nwb_events.py` and the loop at `nwb_inspect.py:1204-1210`. Check: `grep -n '"invalid_times"' jnwb/*.py` returns one site, and `nwb_inspect` imports the shared helper; the 55 tests in `tests/test_nwb_events.py` and the inspect tests stay green.

### 17-167 Non-blocking findings of the 22a2aa68 closure pass

Release: deferred-0.2.18 (non-blocking; `artifacts/evidence/0.2.17/closure_22a2aa68.md`, rows N1 to N4).
Role: docs-harness. Skill: none. Blocked by: N1 waits on Hamm's wording decision. Lane: new `_temp_` lane from `dev`.
Writes: `README.md`, `artifacts/changelog.d/nwb-float32-nan-factors.fixed.md`, `artifacts/changelog.d/*.changed.md` (one new fragment for N2).
- 17-167: N1 README.md:22 states "label permutation requires an exchangeability scheme"; `cluster_permutation_test` defaults `scheme` (`jnwb/statistics/_cluster.py:130-131`). N2 `python -m` self-tests removed in 8af1c58d (`jnwb/artifact_repair.py`, `jnwb/visual_qc.py`) have no fragment. N3 `jnwb.statistics` no longer exposes `np`, `pd`, `log`, `resolve_rng`, `parallel_map` (none in `__all__`). N4 the float32 fragment names `nwb_events.py` but the fix is in `nwb_inspect._to_physical`. Check: N1 resolved by Hamm's wording or the one-clause repair (`grep -n "exchangeability" README.md`); N2 has a fragment naming both files; N4 fragment names `nwb_inspect.py`.

