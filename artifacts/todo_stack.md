# 0.2.14

Items are deleted when done, never ticked; git, `CHANGELOG.md` and the receipts hold history. 0.2.13
closed on 2026-10-21 (tag `v0.2.13`), and its section is gone from this file. The theme and plan of
0.2.14 are in the section below, as ruled 2026-10-19; its checkpoint closes when its table passes
row by row. A 0.2.14 item carries `deferred-0.2.14` in its Release field until the version is bumped to 0.2.14
(`artifacts/evidence/0.2.8/plan/decisions.md` D2).

Theme (ruled 2026-10-19): the public NWB mutation and execution APIs (07-21 and 07-22 landed), and the
existing tools brought to their stated contract: fact closure, reading edges, the pitfall
estimators, the deferred laminar and curation work, and the removals ruled for 0.2.14. The rulings the plan needs come first (wave 0), one
question per message; the checkpoint is the 0.2.13 table with 0.2.14 in place of 0.2.13.

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one clone and one writer; up to three lanes run at once, when they share no file (Hamm 2026-10-10, 2026-10-11, 2026-10-19); a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| Writers (ruled 2026-10-24): Cursor CLI GLM 5.3 flash at high effort for most packets; Muse (opencode) writes and criticises; Haiku 5.5 writes and runs the skill, doc and `match-checker` checks; a writer never verifies its own packet | the actor is never the verifier |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The integrator owns the stacks, `CHANGELOG.md`, `docs/api.md` and every commit and push | packets report the disposition and the changelog text |
| A public signature, an estimand or a skill line goes to Hamm before code, one question per message | public API and skills are Hamm's |
| Match skills (Hamm 2026-10-21): a packet loads `match-code-style` for code and tests, `match-writing-style` for docs, docstrings, stack text and commit messages, and `match-visual-style` for figures and the dashboard, rendered at final size in light and dark; before each commit `match-checker` (check mode) runs on the changed files and the integrator re-checks every number in its diff | numbers and claims stay fixed while the wording is cut |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), the full suite, commit, push, CI green on `dev` at that SHA | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed; `AUTONOMY` and a one-line source or ruling note follow the fields they qualify. A bullet reads
`ID: defect, as input -> observed against expected, with numbers and units. Check: a predicate that
decides it, naming the file and the asserted value. Waits: why it cannot make release evidence
falsely pass.` `Waits:` appears in deferred cycles; `Waits: not stated.` marks a reason no source
gives, for the closure pass to classify. An item holds one defect and one check, in at most eight
lines.

## Lanes

Full suites run one at a time; on the maintainer's machine through its local `suite_lock.py`,
elsewhere as `python -m pytest tests/ -q`.

| Wave | Lane | Items, in order | Writer | Waits for |
|---|---|---|---|---|
| 0 | Proposals | 15-20's prune rule was ruled 2026-10-26; 11-04, 14-07, 13-04, the 11-07 and 12-11 readings and 11-32's cells were ruled 2026-10-20, and 12-06's line endings on 2026-09-29 (LF, one conversion commit) | Muse drafts; Hamm rules | 0.2.13 tagged |
| 1 | M mutation | none left: 07-21's core five and 07-22's execution and cache API landed (CI green on `dev` at f5c55f2b) | integrator | nothing |
| 2 | F facts | 11-07 and 12-11 landed 2026-10-26 (S1, S2, S5, S7 held) | Cursor GLM or Muse writes, Haiku checks | nothing |
| 2 | L laminar | none left: 15-22 landed 2026-10-26, a repository-only skill Hamm accepted | Muse | nothing |
| 2 | X outside code | none left: 12-21's spectrum test landed (delay and direction moved to the roadmap by the 2026-10-23 ruling) and 14-08's rows cite the lab pipeline | Haiku | nothing |
| 2 | D docs and dashboard | reopened 2026-10-24: docs with interactive and still figures and a validation dashboard, after jaxfne's; items follow the preference rulings | Cursor GLM and Haiku for pages and figures, Muse for the dashboard design | the comparison with jaxfne and Hamm's preference rulings |
| 2 | N numerics and I/O (audit 2026-10-25) | none left: every item landed 2026-10-25 | Cursor GLM writes, Haiku checks; one lane per file set | nothing |
| 2 | P process and docs (audit 2026-10-25) | 17-34, 17-36 and 17-58 landed 2026-10-26 | Haiku writes, Muse reviews | nothing |
| 3 | H harness | 12-06, then 17-56; 07-05, 12-07, 17-26, 17-27, 17-30, 17-31, 17-32, 17-41, 17-54, 17-55 and 12-05 landed 2026-10-26, 11-03 went to the roadmap | Haiku | wave 2 merged |
| 3 | Freeze | 16-18, last, after every item that edits a listed body (17-19 among them) | integrator | waves 2 and 3 merged |
| 4 | Checkpoint 0.2.14 | the 0.2.13 checkpoint, for 0.2.14 | integrator | waves 0 to 3 merged |

## Checklist 0.2.14

0.2.14 is released when every row below passes; nothing else is required (ruled 2026-10-24). Rows 1 to 13 are what ships, checked on `dev`; rows 14 to 16 are the release itself, in the order of the checkpoint below. Anything raised during the cycle goes to 0.2.15. A row whose items have left this file still passes only when its check is re-run at the checkpoint.

| # | Holds at release | Check | Items |
|---|---|---|---|
| 1 | The NWB mutation API: the core five, then the execution and cache API, each signature ruled by Hamm before code | `docs/api.md`, `CHANGELOG.md` and the `skills/` routing rows name each symbol; `tests/test_skills_validation.py` passes; each function has a round-trip test on a written file | items gone (07-21, 07-22) |
| 2 | The four pitfall estimators, `noise_correlation` and `screen_units_against_labels`, as ruled 2026-10-20 | each has a planted-case test that recovers the planted value and one that refuses the documented bad input; each cites its source in `docs/references.md` | items gone (14-06, 14-07, 13-04) |
| 3 | `create_aligned_dataset`, `create_result`, `create_figure` and `gpu_pca` are gone | the names are absent from `jnwb.__all__` and `docs/api.md`; `CHANGELOG.md` records each removal | items gone (16-01, 16-02) |
| 4 | Every container `inspect` lists is readable, and the compression, unit-table and addressing edges hold | a test that inspects each fixture and reads every listed container passes | item gone (11-01) |
| 5 | Every fact without a holder gets a scan with a planted case | the harness gate's fact line reports no UNHELD fact naming a 0.2.14 item; each scan fails on its planted case | 12-07, 11-07, 12-11 and 16-10 landed, 11-03 to roadmap (ruled 2026-10-26); 11-09 to roadmap (ruled 2026-10-25) |
| 6 | The laminar and curation work: the curation-default calibration and fusion agreement that can say `agree` or `disagree` | the receipts are committed under `artifacts/benchmarks/calibration/`; the `jnwb-sim-benchmark` skill is a draft Hamm has ruled on | 15-22 and 16-03 landed |
| 7 | The verification inventory and a pruning constraint ruled by Hamm; process tests pruned under it | `artifacts/evidence/0.2.14/verification_inventory.md` is committed; the suite's runtime and test count before and after are in the commit message | 12-06; 07-05, 15-20, 12-05 and 09-07 landed 2026-10-26 |
| 8 | The core freeze and the surface manifest (goal F1, F2) | Gate 19 lists 28 functions; the surface-manifest test passes | 16-18; 16-19 landed |
| 9 | Docs pages carry still and interactive figures, after jaxfne's form (ruled 2026-10-24) | the form and the page set follow Hamm's preference rulings; a test builds each figure from committed inputs; the strict docs build passes | 17-01 landed 2026-10-26 |
| 10 | A validation dashboard after jaxfne's, keeping the proof of work, the HTML outputs and the GLO cards (ruled 2026-10-23 and 2026-10-24) | `tests/test_build_dashboard.py` builds it from committed files with every receipt digest matching; the published page shows each section the preference rulings name, in light and dark | 17-02 landed 2026-10-26 |
| 11 | Reference claims checked against full text where an abstract decides nothing | each claim cell of `docs/references.md` has a ledger line, confirmed, reworded, or cut; the 14 core texts keep their cells (ruled 2026-10-23, ledger ruled 2026-10-25) | ledger: 93 cells, 60 cut, 6 reworded, 13 confirmed, 14 kept, 0 unrecorded; 17-58 landed 2026-10-26 |
| 12 | Release form (`AGENTS.md` §11): low-verbosity docs, low-complexity code, an empty open stack, no required item | `match-checker` runs once at the checkpoint on every file changed since v0.2.13, its report committed (ruled 2026-10-25); the closure pass (checkpoint step 5) finds 0 new blockers | checkpoint steps 1 to 5 |
| 13 | The audit of 2026-10-25 closed | every item 17-09 to 17-56 has left this file | 17-09 to 17-56 |
| 14 | `dev` is green and release-ready | the suite stamp equals HEAD; CI green on `dev` at that SHA; `python scripts/release_gate.py` exits 0 | checkpoint steps 6 and 7 |
| 15 | `main` carries 0.2.14 and the tag | CI green on `main` at the merge SHA; `v0.2.14` points at it; the TestPyPI and verify jobs pass | checkpoint steps 8 and 9 |
| 16 | 0.2.14 is on PyPI and the next cycle is open | PyPI approved by Hamm; a fresh venv installs 0.2.14, imports it and runs the quickstart; release_gate STEP 0a reads no `deferred-0.2.14` | checkpoint steps 10 and 11 |

## Checkpoint 0.2.14

In order; a failed row stops the checkpoint and returns to the lanes. The steps are `.github/CONTRIBUTING.md`
"Releasing" with the R5 ruling (2026-10-19: CI green on `main` at the SHA that is tagged). Merge,
push and tag are authorized (Hamm 2026-10-19); PyPI's environment approval is Hamm's.

Before step 8, merge `main` into `dev`, so the release merge's first parent is in `dev` (release_gate refuses it otherwise; 2026-10-21).

| Step | Command or action | Passes when |
|---|---|---|
| 1 | Read the open stack and this section | `artifacts/open_stack.md` holds no table row; no `###` item above remains |
| 2 | `python scripts/bump_version.py 0.2.14 --date` | the declared version reads 0.2.14 |
| 3 | `python scripts/assemble_changelog.py --version 0.2.14 --date` | `artifacts/changelog.d/` holds no fragment; `CHANGELOG.md` has a 0.2.14 section |
| 4 | `python scripts/measure_peak_memory.py --write` | each growth past 20% and 5 MiB has a reason in `CHANGELOG.md` |
| 5 | Closure pass: a Muse `review` and a Haiku verifier, independently, with the G-04 claims check | `artifacts/process/blocker_fixpoint_receipt.md` names the commit and 0 new release-blocking problems |
| 6 | Full suite, harness gate, docs build; push `dev` | the stamp equals HEAD; CI green on `dev` at that SHA |
| 7 | `python scripts/release_gate.py` | exit 0 |
| 8 | Merge `dev` into `main` with a merge commit; push `main` | CI green on `main` at the merge SHA |
| 9 | Tag `v0.2.14` at that SHA; push the tag | the TestPyPI and verify jobs pass; PyPI waits on Hamm's approval |
| 10 | Install 0.2.14 from PyPI in a fresh venv; import; run the quickstart | the installed version reads 0.2.14 |
| 11 | Move the 0.2.15 roadmap rows here with their full text; 0.2.15 becomes this file's top section | release_gate STEP 0a reads no `deferred-0.2.14` |

### 12-06 No process identifiers outside the stacks

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: nothing.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/workflow.yml`, `.github/CONTRIBUTING.md`.
- 12-06: P-284: `scripts/` and test files cite item and problem ids (P-209 and IB-71 merged; the 2026-10 counts no longer reproduce, so the lane re-measures them); P-102 levels line endings to LF, as D3 ruled 2026-09-29 (82 tracked files are CRLF on 2026-10-25), in one conversion commit. Check: each is removed or rewritten as a plain reason, then gate 14 reads both folders with an allowlist for machine-required literals; gate 16 passes and one byte-mode edit per convention applies. Waits: After 12-05 and 12-07; neither directory ships, and P-102 is bytes only. Moved to 0.2.14 by the 2026-10-19 theme ruling.
Accept: gate 14 passes on `scripts/` and `tests/`; the suite passes.

### 16-18 The core freeze (goal F1)

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `artifacts/process/frozen_validated.json`, `tests/test_frozen_core_mutants.py`.
- 16-18: Six functions are frozen; goal F1 (ruled 2026-10-21) freezes 22 more: `compute_psd`, `band_power`, `aggregate_to_db`, `to_db`, `relative_power`, `harmonic_analysis`, `wpli`, `imaginary_coherency`, `cross_area_coherence`, `granger`, `granger_causality`, `bipolar_reference`, `laplacian_reference`, `current_source_density_1d`, `voltage_curvature_1d`, `cluster_permutation_test`, `clopper_pearson`, `mann_whitney_p_floor`, `shuffle_r2_ci`, `fdr_correct`, `label_layers`, `bin_spikes`. Each enters `artifacts/process/frozen_validated.json` with its body hash, the commit it was verified at and the tests that kill a planted change to it; a reviewer that did not write the test runs the mutant. Frozen last in the cycle, after 14-06 adds its estimators beside `granger` and after every item that edits a listed body (12-11's `_psd.py` edit among them). `fdr_correct`, `clopper_pearson` and `mann_whitney_p_floor` are also `StatisticalAnalysis` methods: the item freezes the definition the other delegates to, and names it. Check: Gate 19 lists 28 functions, and for each a planted body change fails its named tests.

## Audit of 2026-10-25

The items below come from the open stack of 2026-10-25 (`git show e00e8664:artifacts/open_stack.md`; the O- number in each source line traces a row to its probe). Each fix starts with a test that fails on the current code. Rulings: `artifacts/rulings/2026-10-25.md`.

### 17-56 Test files stop appending to `sys.path`

Release: deferred-0.2.14.
Role: jnwb-developer. Skill: none. Blocked by: 12-06 (same files).
Writes: `tests/**/*.py`.
- 17-56: 69 test files append to `sys.path` though `pyproject.toml` sets `pythonpath=["."]`. Check: `git grep -c "sys.path.insert\|sys.path.append" -- tests` reads 0 or each remaining site states why; the suite passes. Source: O-26.
