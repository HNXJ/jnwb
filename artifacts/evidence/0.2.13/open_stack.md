# Open stack (jnwb, 2026-10-17)

Everything open on `dev` after 52f2a17b, grouped by who moves it next. Sources: `artifacts/problem_stack.md` (0 rows), `artifacts/todo_stack.md` (15-11 only), `artifacts/roadmap.md` (35 rows: 30 `deferred-0.2.13`, 5 `deferred-0.2.14`), and the 2026-10-17 re-audit (A: numerical half, 19 probes; A2: I/O half, 11 probes; B: tests and docs).

Closed since 2026-10-15: 15-14, 15-16, 15-21, 11-05, 14-05, 12-24 (`best_dev` fixed; the all-NaN block keeps `unowned`, ruled 2026-10-17); 12-04 (P-238: `collect_selector` keeps ids with a space; P-266: a top-level overwrite is caught, and the branch rebindings and `by_request` paths the gate cannot see are a reviewed inventory, `tests/test_switch_rebinding_is_reviewed.py`); the WaveMAP unit reading (peak-to-peak 31 to 483 in units labelled volts); 09-07's ledger recount and ruling-date check; red dev CI 39080282438 (two scripts asserted the checkout after deferring); audit B's hygiene rows; the non-empty sweep (63 sites: 33 gained floors, 30 are negatives or already floored); unseeded test draws (38 seeded, now gated); P-296 and P-344; audit A's four code rows (the fifth, `_cluster.py` `rng=0`, is the module convention: 11 public functions default `rng` to a plain int); the hard-linked `select=` cast (every name re-pointed, ruled 2026-10-18); A2's F2 and F3 (`inspect` warns on a type no namespace defines, embedded extensions included); `detect_bad_channels` flagging a whole short probe for one dead contact (found while closing audit A). Two candidate actions were dropped: `PYTHON_SUPPORTED` is gate 8's independent declaration that the classifiers are checked against, and the evidence probes that name `C:/workspace/jnwb` are receipts. A2's F1 is not a defect: `unit_census_report` refusing a frame without its metric columns is documented in `skills/jnwb-nwb-data/references/addressing_and_metadata.md` and pinned by `test_tiers_census_and_folds_refuse_or_label_what_their_rows_say`. The `alignment_review_0.2.5.md:197` pointer is a dated receipt for a file that moved in c0c625ab. `scripts/measure_order.py` has a caller (`tests/test_computational_order_sources_agree.py`).

## A. Waits on a ruling by Hamm

| Item | Open question | Source |
|---|---|---|
| 0.2.13 theme | The cycle runs on goal and §11 acceptance until a theme is ruled | `todo_stack.md:9` |
| 15-13 | `vflip2` above 200 um spacing: refuse, or a doc line | roadmap |
| 15-15 | Whether `curate_and_label` runs `vflip2` | roadmap |
| 15-19 | A measured `omega_cut` or a data-driven threshold (recovery 29/100, matched null 24/100) | roadmap |
| 15-17 | The Wishart effective-n | roadmap |
| 15-20, 12-05 | The apparatus bound after the inventory; the prune list | roadmap |
| 07-21, 07-22, 12-13, 12-23, 11-04, 14-06, 14-07, 13-04 | Public API shapes | roadmap |
| 11-32 | Holder cells | roadmap |
| Open rulings | `window` retargeting (2026-09-27); dark plot `theme=` (2026-10-04); showcase publication at Gate B (2026-10-12); which CI run qualifies, dev or main (2026-10-15 R5) | `artifacts/rulings/` |
| Shipped-surface choices | The legacy constructor path names no removal version (`docs/02_paths_addressing_metadata.md:285`); `jrsa(sliding=True)` raises `NotImplementedError`; `bilinear.py` and `nam.py` stay experimental; goal 8 records peak memory with no threshold | scan |
| 12-10 skill gaps | A blind session through the skills missed the tutorial's LFP clock and its dB by 0.08 to 0.21: no skill page puts tick-valued timestamps on session time (the tutorial's `derive_clock` is its own code, so a page or a public function), and none states the `CANONICAL_BANDS` edges. Skill pages change by amendment | `artifacts/evidence/0.2.13/agent_session_dandi000253/` |
| P-335 (07-05) | `curate_and_label`'s defaults are stated working values with no receipt or source, and its inner stages are not public parts: calibrate, cite, or keep as stated; expose the stages or not | `artifacts/evidence/0.2.13/p335_laminar_curation_review.md` |
| `jnwb-sim-benchmark` skill | Proposal only; skills change by amendment | session |

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

| Id | Where | Question |
|---|---|---|
| F-01 | `jnwb/permutation.py:63`, `jnwb/jrsa/_inference.py:147` | The default two-sided rule counts `abs(null) >= abs(obs)`, which assumes a null centred on 0. For a non-negative metric (cosine, MI, TE) a lower-tail observation gets p = 1.0: cosine 0.620 against a null with minimum 0.701 gives 1.0, where the one-sided `less` p is 0.0005. A centred two-sided rule, a per-metric default, or a refusal |
| F-02 | `jnwb/statistics/_firing.py:118` | `n_trials < 2` returns a literal `p_value_fire_shuffle` of 1.0 from a fallback branch (AGENTS.md section 1): NaN with a reason, or refuse |
| F-03 | `jnwb/statistics/_analysis.py:738`, `:791` | `confirmatory_compare` takes no `rng`, so its bootstrap CI always draws from `DEFAULT_SEED` (fact S5 asks for an explicit `rng`; `docs/07_statistical_inference_and_nulls.md:12` says resampling functions take one): add `rng=` to the public signature |
| F-04 | `jnwb/laminar/_vflip2.py:541` | `vflip2_from_lfp` labels PSD column k as k Hz. A trial shorter than `fs` samples pads to 2^n bins about 1.95 Hz apart (512 samples at 1 kHz), and a 20 Hz tone is labelled 10. Compare with vFLIP2.m before repair |
| F-05 | `jnwb/laminar/_vflip2.py:431` | Below `fs` = 300 Hz the columns above Nyquist hold mirrored power (`fs` 250: column 140 equals column 110); only a column past the FFT length raises. Refuse, or guard the band |
| F-06 | `jnwb/jrsa/_metrics.py:256` | Plug-in 32-bin MI with no bias correction: independent inputs give 1.99 nats at N = 60 and 0.32 at N = 1000. Estimator choice |
| F-07 | `jnwb/vis/laminar.py:310`, `:322` | Legend text "Gamma (50–150 Hz)" and "Alpha/Beta (10–30 Hz)" for caller-supplied powers, against `CANONICAL_BANDS` (`spectral/_common.py:63`) and the vFLIP bands; joins the 12-10 band-edge question |
| F-08 | `jnwb/laminar_curation.py:912` | Only grade F clears labels; the docstring (`:684`) says a fit that does not hold carries none, and grade C still emits them |
| F-09 | `jnwb/continuous.py:34` | Window-to-sample conversion uses `round()`, which ties to even ((-0.25, 0.25) s at 10 Hz gives samples [-2, 2)); the tie rule is unstated |
| F-10 | `tests/test_state_basis_is_checked.py:216`, `:259`; `tests/test_state_reconstruction.py:237` | Skip on every CI leg because `artifacts/state.md` is ignored and CI never generates it: generate it in CI, or keep them local |
| F-11 | `.github/workflows/workflow.yml:277` | `test-pandas3` is `continue-on-error`; keep it non-blocking? |
| F-36 | `jnwb/vis/state_space.py:177`, `:205` | `plot_rsm_heatmap`'s default title says "Similarity", its default colour bar and hover "Dissimilarity", and the docstring calls the input neither: change the `colorbar_title` default to "Similarity", or the title |
| F-55 | `jnwb/statistics/_trials.py` `assign_subblock_quartiles` | A NaN `start_time` lands in the last quartile (`[0, 3, 1, 2]`): refuse it like `detect_trial_cycles`, or keep the order rule |

### F2. Executable by agents

Closed 2026-10-18: F-12 to F-17, F-19, F-21, F-23, F-29, F-31 to F-35, F-38 to F-40, F-42, F-43, and two items of F-53. F-37 was shown false: `vflip_from_lfp` treats a channel with a NaN sample as bad, as its docstring says. A non-finite trial start is now refused at seven sites, checked by `tests/test_nonfinite_trial_starts_are_refused.py`.

| Id | Sev | Where | Defect |
|---|---|---|---|
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

Unconfirmed, kept for the next pass: non-finite null draws counted in n (`jrsa/_inference.py:145`); `test_laminar_curation.py:194` accepts any contact but 20; `test_jrsa_correctness.py:232` records the correction, not its effect; `test_nwb_integrity.py:565` pins pynwb's wrong-block read; `artifact_repair.py:57` IndexError on empty input; `nwb_io.py:150` bytes column names; `compression.py:459` a reference left raw when its target is absent; `docs/10_operation_specifications.md:91` `aggregate_over=0` against the signature's None.
