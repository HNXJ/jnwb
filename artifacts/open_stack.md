# Open stack (jnwb, 2026-10-17)

Everything open on `dev` after 52f2a17b, grouped by who moves it next. Sources: `artifacts/problem_stack.md` (0 rows), `artifacts/todo_stack.md` (15-11 only), `artifacts/roadmap.md` (35 rows: 30 `deferred-0.2.13`, 5 `deferred-0.2.14`), and the 2026-10-17 re-audit (A: numerical half, 19 probes; A2: I/O half, 11 probes; B: tests and docs).

Closed since 2026-10-15: 15-14, 15-16, 15-21, 11-05, 14-05, 12-24 (`best_dev` fixed; the all-NaN block keeps `unowned`, ruled 2026-10-17); 12-04 (P-238: `collect_selector` keeps ids with a space; P-266: a top-level overwrite is caught, and the branch rebindings and `by_request` paths the gate cannot see are a reviewed inventory, `tests/test_switch_rebinding_is_reviewed.py`); the WaveMAP unit reading (peak-to-peak 31 to 483 in units labelled volts); 09-07's ledger recount and ruling-date check; red dev CI 39080282438 (two scripts asserted the checkout after deferring); audit B's hygiene rows; the non-empty sweep (63 sites: 33 gained floors, 30 are negatives or already floored); unseeded test draws (38 seeded, now gated); P-296 and P-344; audit A's four code rows (the fifth, `_cluster.py` `rng=0`, is the module convention: 11 public functions default `rng` to a plain int); the hard-linked `select=` cast (every name re-pointed, ruled 2026-10-18); A2's F2 and F3 (`inspect` warns on a type no namespace defines, embedded extensions included); `detect_bad_channels` flagging a whole short probe for one dead contact (found while closing audit A). Two candidate actions were dropped: `PYTHON_SUPPORTED` is gate 8's independent declaration that the classifiers are checked against, and the evidence probes that name `C:/workspace/jnwb` are receipts. A2's F1 is not a defect: `unit_census_report` refusing a frame without its metric columns is documented in `skills/jnwb-nwb-data/references/addressing_and_metadata.md` and pinned by `test_tiers_census_and_folds_refuse_or_label_what_their_rows_say`. The `alignment_review_0.2.5.md:197` pointer is a dated receipt for a file that moved in c0c625ab. `scripts/measure_order.py` has a caller (`tests/test_computational_order_sources_agree.py`).

## A. Waits on a ruling by Hamm

Ruled 2026-10-19 (`artifacts/rulings/2026-10-19.md`): the 0.2.13 theme, 15-13, 15-15, 15-17, 15-19, 15-20 and 12-05, 12-13, 12-23's permutation half, the open rulings (`window`, Gate B, R5; the dark `theme=` was ruled 2026-10-04), the shipped-surface choices, 12-10, P-335 and the `jnwb-sim-benchmark` skill. 07-21 and 07-22 were ruled 2026-09-29 and move to 0.2.14.

| Item | Open question | Source |
|---|---|---|
| 11-04, 14-06, 14-07, 13-04 | Public API shapes, all `deferred-0.2.14` | roadmap |
| 12-23, second half | A percentile bootstrap over mice: a shape for `bootstrap_ci`, or the showcase keeps its own | roadmap |
| 11-32 | Holder cells; ruled 2026-10-11 to wait with 09-04 and 10-10 | roadmap |
| Goal 8 text | `artifacts/goal.md` is Hamm's: the 20% peak-memory rule of 2026-10-19 needs his edit there | rulings 2026-10-19 |

## B. Executable by agents now

| Item | Next step | Source |
|---|---|---|
| 11-02 | `classify_layer_from_depth` waits on D10's ruling; the `select=` cast is in section A; P-348, P-192, P-296 and P-344 closed 2026-10-17 | roadmap |
| 07-05 | Downstream paper agent | roadmap |
| 09-07, 12-06 | 09-07's second-home check (the second needs a forbidden-phrase column in the rulings tables, Hamm's files); 12-06 waits on 12-05, 12-07, 12-08 | roadmap |
| Strict xfails | Word-pattern misses are the heuristic's documented limit; the mobile-width ledger is a figure-size choice | `tests/test_skill_decline_behaviour.py`, `tests/test_figure_form.py` |
| Fact closure group | 10-10, 11-06, 09-04, 11-07, 12-11, 11-03, 11-09, 12-08, 12-07: ruled to wait; facts report UNHELD, nothing public claims them | roadmap |

## C. Waits on someone outside the repository

| Item | Waits on | Source |
|---|---|---|
| 15-11 second half | Andre Bastos's simulation code; the todo stack cannot empty before it | todo stack |
| 12-21 | jaxfne's excerpt | roadmap |
| 14-08 | The lab pipeline's code | roadmap |
| Metal path, GPU tests | Hardware | `jnwb/_backend.py:40`, `tests/test_adversarial_inputs.py:122` |

## D. Housekeeping

| Item | State |
|---|---|
| Local branches | 11 (`dash-app`, `dash-gen`, `dash-pages`, `lane-k1`, `lane-k3`, `lane-m`, `lane-w`, `lane-y2`, `_temp_never-sweep`, `main`, `dev`) |
| Worktrees | `C:/workspace/jnwb` (dev), `C:/workspace/_temp_jnwb-main` (main) |
| `E:/repos/jnwb` | Rename to `_temp_` blocked by a handle no unelevated scan finds |
| Unreleased fragments | 14 in `artifacts/changelog.d/` |
| Data correction | V3v on ses-260724 (omission project) |

## E. Useful actions, none blocking

None open.

## F. Audit 2026-10-18 (baseline 8263a944)

Eight read-only passes, two efforts per lane (L1 numerics, L2 data and laminar, L3 docs, skills and vis, L4 tests, scripts and CI), with probes under the session scratchpad. Each row was demonstrated by a probe. The dispatcher re-read the cited source for F-01 to F-05, F-07, F-12 to F-15, F-17, F-18, F-23, F-31, F-32, F-34 to F-36 and F-38 to F-40; the other rows rest on the workers' probe output. Shown false and dropped: `n_edges` halving (the analyzer halves only a symmetric correlation matrix), two skips that are tripwires for a future signature, the helper-name imports (the import is the assertion). Already on record and not repeated: the all-NaN `unowned` block (ruled 2026-10-17), `vflip2` above 200 um (15-13).

### F1. Waits on a ruling

None. F-07 was ruled 2026-10-18; F-09, F-10, F-28 and F-36 on 2026-10-19 (`artifacts/rulings/2026-10-19.md`). F-08 was shown false (C and D labels are documented sensitivity checks); F-11 closed as documented (`workflow.yml:272`, hdmf caps pandas below 3); F-55 is refused under the non-finite-start rule.

### F2. Executable by agents

Closed 2026-10-19: G-01 (c3addf1f and the skill clause ruled 2026-10-19); F-10, F-20, F-22, F-24, F-49, F-61 (37775ce4, 1ab48ae1); F-01 to F-07, F-09, F-25 to F-28, F-30, F-36, F-46 to F-48, F-55, F-56 (b286db16, 9dc35302, 5b5184f2, 62a0708f, 25e452d2, c8f70616); G-02 and G-03 (d1af0665). Closed 2026-10-18: F-12 to F-17, F-19, F-21, F-23, F-29, F-31 to F-35, F-38 to F-40, F-42, F-43, and two items of F-53. F-37 was shown false: `vflip_from_lfp` treats a channel with a NaN sample as bad, as its docstring says. A non-finite trial start is now refused at seven sites, checked by `tests/test_nonfinite_trial_starts_are_refused.py`.

| Id | Sev | Where | Defect |
|---|---|---|---|
| F-18 | med | `jnwb/jrsa/_backends.py:86` | Complex input is cast to float64 and the imaginary part dropped, with only numpy's ComplexWarning |
| F-41 | med | `tests/test_api_md_is_interpreter_independent.py:145` | The cross-interpreter byte check never runs in CI (no `JNWB_MATRIX_PYTHONS`; Linux legs have no `py`) |
| F-44 | low | `jnwb/jrsa/_stages.py:404`, `:349` | An integer window width is off by one (5 gives 4 samples); the standardize warning says it "overrides and negates" normalize, and the output stays in [0, 1] |
| F-45 | low | `jnwb/jrsa/_metrics.py:30`, `:50`, `:125` | The 1e-12 offset gives t = 4.2e6 at abs(r) = 1 (exact inf); the metric helpers truncate mismatched rows (unreachable through `jrsa`) |
| F-54 | low | tests | The omission-boundary comparison skips on every CI leg (`test_addressing.py:568`): it needs the `omission` package, which no CI leg installs, and no committed fixture stands in |
| F-64 | med | `artifacts/benchmarks/calibration/curation_calibration_0.2.13.md` | Every swept value of all 15 `curate_and_label` defaults gives the same counts (5 of 24 planted anchors within one pitch of 100 z0, 0 of 24 nulls graded A or B), so "FLAGGED: none" tests nothing; the anchor misses by -420 to +917 um on `synth_vflip2_crossover` probes |

Unconfirmed, kept for the next pass: non-finite null draws counted in n (`jrsa/_inference.py:145`); `test_laminar_curation.py:194` accepts any contact but 20; `test_jrsa_correctness.py:232` records the correction, not its effect; `test_nwb_integrity.py:565` pins pynwb's wrong-block read; `artifact_repair.py:57` IndexError on empty input; `nwb_io.py:150` bytes column names; `compression.py:459` a reference left raw when its target is absent; `docs/10_operation_specifications.md:91` `aggregate_over=0` against the signature's None.

## G. External snapshot audit 2026-10-19 (sol-critic, a zip of `origin/dev` before 62a0708f)

F02 (vflip2 above 200 um) was repaired in 62a0708f; F03's agreement half is shown false (`fuse_laminar_anchors` emits only `unresolved` or `unavailable` and caps the grade at B, `jnwb/laminar_curation.py:406`); F04 was the reviewer's environment (pynwb and pytest-xdist absent); F05 was repaired in `artifacts/todo_stack.md`; F06 is 15-11, blocked on outside code; F07 is a property of a zip, covered by the R5 ruling.

| Id | Sev | Where | Defect |
|---|---|---|---|
| G-04 | med | release closure | Audit F08: the closure pass checks each advertised scientific claim against the deferred rows, not only the deferred labels |
