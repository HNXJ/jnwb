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
| Unreleased fragments | 14 in `artifacts/changelog.d/` |
| Data correction | V3v on ses-260724 (omission project) |

## E. Useful actions, none blocking

None open.

## F. Audit 2026-10-18 (baseline 8263a944)

Eight read-only passes, two efforts per lane (L1 numerics, L2 data and laminar, L3 docs, skills and vis, L4 tests, scripts and CI), with probes under the session scratchpad. Each row was demonstrated by a probe. The dispatcher re-read the cited source for F-01 to F-05, F-07, F-12 to F-15, F-17, F-18, F-23, F-31, F-32, F-34 to F-36 and F-38 to F-40; the other rows rest on the workers' probe output. Shown false and dropped: `n_edges` halving (the analyzer halves only a symmetric correlation matrix), two skips that are tripwires for a future signature, the helper-name imports (the import is the assertion). Already on record and not repeated: the all-NaN `unowned` block (ruled 2026-10-17), `vflip2` above 200 um (15-13).

### F1. Waits on a ruling

None. F-07 was ruled 2026-10-18; F-09, F-10, F-28 and F-36 on 2026-10-19 (`artifacts/rulings/2026-10-19.md`). F-08 was shown false (C and D labels are documented sensitivity checks); F-11 closed as documented (`workflow.yml:272`, hdmf caps pandas below 3); F-55 is refused under the non-finite-start rule.

### F2. Executable by agents

Closed 2026-10-18: F-12 to F-17, F-19, F-21, F-23, F-29, F-31 to F-35, F-38 to F-40, F-42, F-43, and two items of F-53. F-37 was shown false: `vflip_from_lfp` treats a channel with a NaN sample as bad, as its docstring says. A non-finite trial start is now refused at seven sites, checked by `tests/test_nonfinite_trial_starts_are_refused.py`.

| Id | Sev | Where | Defect |
|---|---|---|---|
| F-07, F-09, F-10, F-36, F-55 | med | see F1 | Implement as ruled: F-07 `gamma_band` and `alphabeta_band` keywords; F-09 the right-open containment rule; F-10 one CI leg generates `state.md`; F-36 the RDM title; F-55 a NaN `start_time` refused |
| F-01 to F-06 | high to med | `permutation.py`, `jrsa`, `statistics/_firing.py`, `statistics/_analysis.py`, `laminar/_vflip2.py`, `jrsa/_metrics.py` | Ruled 2026-10-18 (`artifacts/rulings/2026-10-18.md`): the two-sided p is twice the smaller tail; NaN p below 2 trials; `rng=` on the two compare functions; `vflip2_from_lfp` refuses bins coarser than 1 Hz and `fs` below 300 Hz; the MI bias is documented |
| F-18 | med | `jnwb/jrsa/_backends.py:86` | Complex input is cast to float64 and the imaginary part dropped, with only numpy's ComplexWarning |
| F-20 | med | `jnwb/spectral/_psd.py:586` | `aperiodic_fit` r_squared on a flat spectrum is round-off over round-off (0.91 fixed, -1.5e9 knee); `spectral_tilt` returns NaN there |
| F-22 | med | `jnwb/permutation.py:138`, `:152` | A NaN group label never matches `groups == g`, so its labels are never permuted and nothing is refused |
| F-24 | med | `jnwb/onset_fitting.py:259` | A valid `min_amplitude` above the rise raises scipy's "initial guess outside bounds" |
| F-25 | med | `jnwb/addressing.py:354`, `:621` | The area split keys on group_name else location, `enrich` on group_name else probe: one geometry, two area maps |
| F-26 | med | `jnwb/addressing.py:352`, `:365` | An unmatched or None probe key gives every contact the first listed area, silently |
| F-27 | med | `jnwb/addressing.py:680` | `enrich` coerces string unit ids to NaN |
| F-28 | med | `jnwb/metadata.py:790` | `audit_electrodes` keeps only the first area of a multi-area label ("V1, V2") |
| F-30 | med | `jnwb/metadata.py:1072` | `old_new_summary_table` drops units with a missing area (`groupby` dropna; `unit_census_report` keeps them) |
| F-41 | med | `tests/test_api_md_is_interpreter_independent.py:145` | The cross-interpreter byte check never runs in CI (no `JNWB_MATRIX_PYTHONS`; Linux legs have no `py`) |
| F-44 | low | `jnwb/jrsa/_stages.py:404`, `:349` | An integer window width is off by one (5 gives 4 samples); the standardize warning says it "overrides and negates" normalize, and the output stays in [0, 1] |
| F-45 | low | `jnwb/jrsa/_metrics.py:30`, `:50`, `:125` | The 1e-12 offset gives t = 4.2e6 at abs(r) = 1 (exact inf); the metric helpers truncate mismatched rows (unreachable through `jrsa`) |
| F-46 | low | `jnwb/addressing.py:228`, `:313` | A peak channel id is truncated by `int(float())` (2.7 gives 2) |
| F-47 | low | `jnwb/nwb_events.py:69` | `/intervals/<t>/codes` keeps the last segment, and the error names the wrong table |
| F-48 | low | `jnwb/artifact_repair.py:92` | A one-sample interval at an edge is skipped silently |
| F-49 | low | `jnwb/testing/synth.py:146` | A fixed 200-sample burn-in starts at 0.40 of the stationary variance (tau 0.5 s, fs 1 kHz); the docstring says stationary |
| F-50 | low | `jnwb/unit_quality.py:681`, `jnwb/spiking.py:422`, `jnwb/continuous.py:114` | One or two spikes give contamination 0.0 with no reason; descending LFP timestamps drop every spike and the warning names the wrong window; an invalid `onset_unit` passes when onsets are empty |
| F-51 | low | `jnwb/vis/canvas.py:112`, `:132`; `jnwb/vis/hierarchy.py:188` | "maximum 235 mm" only warns; `int()` maps rank 0.5 to '0' |
| F-52 | low | docstrings | `gaussian_smooth_rate` returns float64 for float32 (`spiking.py:592`); `fdr_correct` flattens 2-D input against "same shape" (`statistics/_analysis.py:15`); `rng=1.5` with a seed raises ValueError, documented TypeError (`permutation.py:187`); `morlet_wavelet` "exactly for n_cycles >= 3" (0.99972 to 1.00004, `tfr.py:102`); the spectral-average Granger "returns the time-domain value" (0.0577 against 0.0601, `connectivity/_granger.py:866`); "No floor" above a 1e-4 floor (`laminar/_vflip.py:704`) |
| F-53 | low | docs and skills | `stream_npz_array` promises TypeError and raises IndexError (`docs/10_operation_specifications.md:118`); `lfp` against `lfp_data` and a call without `fs` (`docs/10_operation_specifications.md:121`, `docs/03_representational_similarity_jrsa.md:33`); the anchor at `common_mistakes.md:438` fails GitHub's slug; landmark-viz `SKILL.md:49` shows a label the code never draws |
| F-54 | low | tests | `isinstance`-only assertions under names that claim a value (`test_statistics_api_split.py:144`, `test_connectivity.py:405`; both values are pinned elsewhere); the GPU-fallback warning runs only without a GPU (`test_spectral.py:1376`); the omission-boundary comparison skips on every CI leg (`test_addressing.py:568`); the no-verbose path never runs (`test_release_recovery_gates.py:65`); `test_jrsa_no_fabricated_failures.py:3` cites `artifacts/.lab/`, which does not exist |
| F-56 | low | `jnwb/connectivity/_granger.py:34`, `jnwb/laminar/_xflip.py:672`, `jnwb/testing/synth.py:200` | NaN passes the guard of `ridge` (returns NaN), `n_surrogates` (no error) and `freq_hz` (300 non-finite samples) |
| F-57 | low | `jnwb/vis/spectral.py:64`; `plot_granger_spectra`, `plot_rsm_heatmap`, the `ci_*` arguments in `vis/laminar.py`, `sig_mask` in `vis/spectral.py` | The NaN colour range of F-34 in `plot_spectral_modulation_matrix`; no shape check against the axes; an empty string `SOURCE ARTIFACTS` passes as `[""]` |
| F-58 | med | `jnwb/vis/laminar.py:159`, `:478` | A crossover or layer boundary outside the depth range is dropped with no warning (1200 um on mm depths draws nothing) |
| F-59 | med | `jnwb/vis/hierarchy.py:107`, `:137`, `:171` | A NaN gives a NaN fit line and annotation with no warning; error-bar lengths go negative when a CI does not bracket its value; the annotation sits below the data when every `ci_high` is negative |
| F-60 | med | `jnwb/vis/spiking.py:294`, `:70` | `plot_sorted_heatmap` accepts a `time_ms` of the wrong length; a sixth condition reuses the first colour |
| F-61 | med | `docs/04_spectral_analysis_and_tfr.md:142` | The documented `aperiodic_fit` example passes the 0 Hz bin from `compute_psd` and raises |
| F-62 | low | docs and comments | `docs/04_spectral_analysis_and_tfr.md:52` calls the `normalize=True` result a ratio (it is dB); `docs/02_paths_addressing_metadata.md:169` says a missing metric makes a unit Unknown (with a critical failure it is Poor); `CHANGELOG.md:96` contradicts itself on the bound at U = 5 and 6; `vis/theme.py:26` says 8 colours (9); `vis/hierarchy.py:105` says robust (OLS); `vis/laminar.py:348` crossover x_max is NaN when a trace holds NaN |

Unconfirmed, kept for the next pass: non-finite null draws counted in n (`jrsa/_inference.py:145`); `test_laminar_curation.py:194` accepts any contact but 20; `test_jrsa_correctness.py:232` records the correction, not its effect; `test_nwb_integrity.py:565` pins pynwb's wrong-block read; `artifact_repair.py:57` IndexError on empty input; `nwb_io.py:150` bytes column names; `compression.py:459` a reference left raw when its target is absent; `docs/10_operation_specifications.md:91` `aggregate_over=0` against the signature's None.

## G. External snapshot audit 2026-10-19 (sol-critic, a zip of `origin/dev` before 62a0708f)

F02 (vflip2 above 200 um) was repaired in 62a0708f; F03's agreement half is shown false (`fuse_laminar_anchors` emits only `unresolved` or `unavailable` and caps the grade at B, `jnwb/laminar_curation.py:406`); F04 was the reviewer's environment (pynwb and pytest-xdist absent); F05 was repaired in `artifacts/todo_stack.md`; F06 is 15-11, blocked on outside code; F07 is a property of a zip, covered by the R5 ruling.

| Id | Sev | Where | Defect |
|---|---|---|---|
| G-01 | high | `skills/`, `docs/` | Audit F01: no sweep yet shows that no page claims more for an accepted vflip2 fit than the docstring now does (18 of 100 noise-only accepted; an accepted fit is not by itself evidence of a crossover) |
| G-02 | med | `tests/test_vflip2.py` | Audit F02: the spacing bound is tested at 200 and 200.5 um only; add 199 and 201 um and a reversed-orientation case |
| G-03 | med | `jnwb/laminar_curation.py`, `docs/10_operation_specifications.md` | Audit F03: `curate_and_label` passes no vflip2 anchor to the fusion and docs/10 does not say so; the repair is the 15-15 ruling |
| G-04 | med | release closure | Audit F08: the closure pass checks each advertised scientific claim against the deferred rows, not only the deferred labels |
