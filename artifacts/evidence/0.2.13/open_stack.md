# Open stack (jnwb, 2026-10-17)

Everything open on `dev` after 52f2a17b, grouped by who moves it next. Sources: `artifacts/problem_stack.md` (0 rows), `artifacts/todo_stack.md` (15-11 only), `artifacts/roadmap.md` (35 rows: 30 `deferred-0.2.13`, 5 `deferred-0.2.14`), and the 2026-10-17 re-audit (A: numerical half, 19 probes; A2: I/O half, 11 probes; B: tests and docs).

Closed since 2026-10-15: 15-14, 15-16, 15-21, 11-05, 14-05, 12-24's `best_dev` half; audit B's hygiene rows; audit A's four code rows (the fifth, `_cluster.py` `rng=0`, is the module convention: 11 public functions default `rng` to a plain int); A2's F2. A2's F1 is not a defect: `unit_census_report` refusing a frame without its metric columns is documented in `skills/jnwb-nwb-data/references/addressing_and_metadata.md` and pinned by `test_tiers_census_and_folds_refuse_or_label_what_their_rows_say`. The `alignment_review_0.2.5.md:197` pointer is a dated receipt for a file that moved in c0c625ab. `scripts/measure_order.py` has a caller (`tests/test_computational_order_sources_agree.py`).

## A. Waits on a ruling by Hamm

| Item | Open question | Source |
|---|---|---|
| 0.2.13 theme | The cycle runs on goal and §11 acceptance until a theme is ruled | `todo_stack.md:9` |
| 12-24 | An all-NaN block: "unowned" (the 2026-10-10 ruling) or "unknown", in both layouts | roadmap |
| 15-13 | `vflip2` above 200 um spacing: refuse, or a doc line | roadmap |
| 15-15 | Whether `curate_and_label` runs `vflip2` | roadmap |
| 15-19 | A measured `omega_cut` or a data-driven threshold (recovery 29/100, matched null 24/100) | roadmap |
| 15-17 | The Wishart effective-n | roadmap |
| 15-20, 12-05 | The apparatus bound after the inventory; the prune list | roadmap |
| 07-21, 07-22, 12-13, 12-23, 11-04, 14-06, 14-07, 13-04 | Public API shapes | roadmap |
| 11-32 | Holder cells | roadmap |
| Open rulings | `window` retargeting (2026-09-27); dark plot `theme=` (2026-10-04); showcase publication at Gate B (2026-10-12); which CI run qualifies, dev or main (2026-10-15 R5) | `artifacts/rulings/` |
| Shipped-surface choices | The legacy constructor path names no removal version (`docs/02_paths_addressing_metadata.md:285`); `jrsa(sliding=True)` raises `NotImplementedError`; `bilinear.py` and `nam.py` stay experimental; goal 8 records peak memory with no threshold | scan |
| `jnwb-sim-benchmark` skill | Proposal only; skills change by amendment | session |

## B. Executable by agents now

| Item | Next step | Source |
|---|---|---|
| 11-01 (with A2 F3) | `inspect` flags a `neurodata_type` no reader knows; needs the reader's known-type set exposed without breaking embedded extensions | roadmap, audit A2 |
| 11-02 | Compression, unit-table and addressing edges | roadmap |
| 12-10, 07-05 | One unfamiliar dataset through the skills; downstream paper agent | roadmap |
| 12-04, 09-07, 12-06 | Gate reach, defect-class checks, process identifiers (re-measure 12-06's counts first) | roadmap |
| Strict xfails | Word-pattern misses; mobile-width AWAITING ledger | `tests/test_skill_decline_behaviour.py`, `tests/test_figure_form.py` |
| WaveMAP units | Volts vs microvolts reading of source labels | `docs/tutorials/10_wavemap.md:20` |
| Fact closure group | 10-10, 11-06, 09-04, 11-07, 12-11, 11-03, 11-09, 12-08, 12-07: ruled to wait; facts report UNHELD, nothing public claims them | roadmap |

## C. Waits on someone outside the repository

| Item | Waits on | Source |
|---|---|---|
| 15-11 second half | Andre Bastos's simulation code; the todo stack cannot empty before it | todo stack |
| Issues #32, #33 | A. Bastos's answer to the review | `artifacts/rulings/2026-10-13.md:14` |
| 12-21 | jaxfne's excerpt | roadmap |
| 14-08 | The lab pipeline's code | roadmap |
| Metal path, GPU tests | Hardware | `jnwb/_backend.py:40`, `tests/test_adversarial_inputs.py:122` |

## D. Housekeeping

| Item | State |
|---|---|
| Local branches | 11 (`dash-app`, `dash-gen`, `dash-pages`, `lane-k1`, `lane-k3`, `lane-m`, `lane-w`, `lane-y2`, `_temp_never-sweep`, `main`, `dev`) |
| Worktrees | `C:/workspace/jnwb` (dev), `C:/workspace/_temp_jnwb-main` (main) |
| `E:/repos/jnwb` | Rename to `_temp_` blocked by a handle no unelevated scan finds |
| Unreleased fragments | 10 in `artifacts/changelog.d/` |
| Data correction | V3v on ses-260724 (omission project) |

## E. Useful actions, none blocking

| Action | Why |
|---|---|
| Derive `PYTHON_SUPPORTED` from `pyproject.toml` | one source for the interpreter set (fact R6) |
| A shared non-empty assertion helper for tests | audit B found `all(...)` over possibly-empty lists twice |
| An exact-case pointer check | a pointer that resolves only on a case-insensitive filesystem passes on Windows |
| Move evidence probes that hard-code `C:/workspace/jnwb` to repository-relative paths | they fail in any other clone |
| `detect_bad_channels` on few independent contacts | 6 white-noise contacts flag all 6 through the iterative cascade; 16 flag only a dead one. Correlated LFP is the documented input; a doc line or a minimum-contact note may help |
| Size-1 dimensions in `nwb_inspect` layout resolution | a `(1, 1)` series raises `AmbiguousLayoutError` though both readings agree; documented and safe |
