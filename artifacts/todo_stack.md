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
Role: jnwb-developer. Skill: none. Blocked by: 17-144-src (open stack). Provenance UNKNOWN, not verified absent (2026-11-25): absent in this machine's clones and bundle tips, in the Windows user tree (13 repositories readable), and on `main-vmac` (its checked scope); origin has none. Sweep of 2026-11-25 (read-only; `/mnt/c/Windows`, the user Temp and Packages folders, the Recycle Bin and System Volume Information on each drive (Recycle Bins: no git store; System Volume Information: existence only), `/mnt/h,i,k` below depth 6, every jaxfne-named directory under `/mnt`): 340 valid repositories under Temp and Packages, 106 valid under jaxfne-named directories (the worker's count; the independent re-scan did not reproduce it, see the 17-144 evidence, section 5), and no git store holding the three SHAs. Bundles: 22 fetched to a scratch repository, none holds them; `jaxfne.bundle` (109 heads) fetches its `dev` head only: object `4d049f8c` is missing from its history although it claims a complete history, its other 108 heads were unverified until the object-level check of 2026-11-25 (evidence section 7: the pack holds 41,903 objects, none of the three). Full record: `artifacts/evidence/0.2.17/17-144_provenance.md`. `E:/cl-jnwb16e` is absent from every `/mnt` drive.
Writes: `artifacts/benchmarks/realdata/isi_cv_recompute.py`, `artifacts/benchmarks/realdata/isi_cv_recompute_receipt.json`, `artifacts/benchmarks/realdata/build_isi_cv_fixture.py`, `tests/fixtures/isi_cv_realdata_subsample.json`, `tests/test_isi_cv_realdata.py`.
- 17-144: three 16-12 commits on `E:/cl-jnwb16e` (0e06993c, 9980f58d, 5fa63dd3) for jaxfne-orchestrator.
  Observed 2026-11-12: path missing; SHAs absent from this clone and `origin`. Check: each on `dev` in that
  order, suite passes, jaxfne-orchestrator told.


