# 0.2.10

Opened 2026-10-05, after 0.2.9 was published. Items are deleted when done, never ticked; git,
`CHANGELOG.md` and the receipts hold history. The previous cycle's record is
`artifacts/archive/0.2.9/todo_stack_0.2.9.md`, with its closure receipt beside it; its 0.2.9
section held only the two release-step items at the release, and every later section moves here
unchanged.

Theme: oversized modules become small packages behind the same public API, and the scientific
edges in them are closed.

Acceptance: `AGENTS.md` §11; `jnwb.__all__` and every public signature identical to 0.2.9;
gate 19 entries re-pointed with unchanged hashes; each estimator change carries a calibration
record in `artifacts/evidence/0.2.10/`.

Every item here carries `deferred-0.2.10`, the deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.9 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## How this stack is executed

| Rule | Why |
|---|---|
| `AUTONOMY: max` unless an item says otherwise (`AGENTS.md` §12) | actor and critic sequence the work |
| One item per packet, in the contract of `artifacts/skills/jnwb-fact-action` §5; role `jnwb-developer` unless named | a batched packet redefines the hard item |
| A lane is one worktree and one writer; at most three lanes run at once; a lane's items run in the order listed | lanes never share a file, so they merge without conflict |
| A packet reproduces each bullet on its own tree first; a bullet that does not reproduce is deleted | non-reproduction is a result |
| The actor is never the verifier | every repair is re-run by someone else |
| The integrator owns the stacks, `CHANGELOG.md` and `docs/api.md` | packets report the disposition and the changelog text |
| Wave barrier: `python scripts/harness_gate.py` (count PASS lines), `python -m pytest tests/ -q`, commit, push, CI green on `dev` | a local pass is not a CI pass |

Item fields: `Release`, `Role`, `Skill`, `Blocked by`, `Writes`, then `Do`, `Accept`, `Stop` as
needed. A bullet reads `ID: defect. Check: what closes it.` Bullets in a deferred cycle end with
`Waits:` and the reason it cannot make release evidence falsely pass.

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| F spectral and laminar | 10-03, 10-04, 10-13 | the shared tests that hard-code module paths, `scripts/mutation_harness.py`, `jnwb/spectral*`, `jnwb/tfr*`, `jnwb/laminar*`, their tests, the calibration scripts, `skills/jnwb-lfp-spectral/SKILL.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`, `docs/laminar.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/compression.py` |
| G connectivity and similarity | 10-05, 10-06 | `jnwb/connectivity*`, `jnwb/jrsa*`, `jnwb/rsa.py`, their tests, `tests/test_substitution_class_sweep.py`, `tests/test_connectivity_pitfalls.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md` once 10-03 is merged, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| H statistics, spiking and decoding | 10-07, 10-08 | `jnwb/statistics*`, `jnwb/permutation.py`, `jnwb/spiking.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/trajectory.py`, `jnwb/gpu_pca.py`, `jnwb/bilinear.py`, `jnwb/nam.py`, `jnwb/artifact_repair.py`, `jnwb/_spread.py`, `jnwb/_bins.py`, `jnwb/_dictlike.py`, `jnwb/paths.py`, `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/testing/**`, `artifacts/frozen_validated.json`, their tests, the statistics, spiking, landmark-viz and figures skills, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md` |

10-01 and 10-02 are merged, so 10-03, 10-04, 10-05 and 10-07 are open.

### 10-03 Spectral edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: none.
Writes: `jnwb/spectral/**`, `jnwb/tfr.py`, `jnwb/tfr_accumulator.py`, `tests/test_spectral.py`, `tests/test_tfr*.py`, `tests/test_gpu*.py`, `skills/jnwb-lfp-spectral/SKILL.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`, `scripts/mutation_harness.py`, `tests/test_mutation_harness_validity.py`.
- P-203: `relative_power(model="log_ratio")` retypes `10*log10`. Check: it calls `to_db`. Waits: same formula.
- P-230: `aperiodic_fit` fits without removing peaks (graded keep, 2026-09-25). Check: an opt-in `remove_peaks=`, default unchanged. Waits: documented.
- P-340: `compute_psd` and `compute_multitaper_psd` return 1e-33 residue for a constant trace. Check: exact zero or the residue documented. Waits: no positivity guard to mislead.
- P-349 device half: CPU and CUDA `wpli` differ for a channel one ulp from constant. Check: parity below working precision declared undefined. Waits: one-ulp edge.
- P-331 coherence half: the coherence residual-variance guard sees detrend residue. Check: a stated tolerance. Waits: degenerate input.
- P-171: the density test's name promises what `test_band_power_is_the_mean_psd_over_the_band` catches. Check: rename. Waits: name only.
- IB-60: the coherence GPU-fallback test compares only p and spectrum. Check: the shift list equals the CPU run's. Waits: the numbers invariant 6 protects are equal.
- P-257: `ComplexTFR(device=...)` accepts any string. Check: a checked device. Waits: only a hand-built `ComplexTFR`.
- P-347: `TFRAccumulator.mean` returns a copy. Check: the docstring and a test. Waits: stated; no user.
- P-287: the trial-mean view check reads one level deep. Check: nested lists and memoryviews refused or copied under the ruled limit. Waits: copies under the ruled limit.
- Deprecations to complete: `spectral_tilt`'s `exponent` key is removed, and `relative_power` raises `ValueError` for a lower-dimension baseline. Check: both land with a CHANGELOG entry. Waits: ruled to land one release after the warning.
- Generator seeds and `jrsa` axes, spectral part: `cross_area_coherence` records no seed for a `Generator`. Check: a child seed recorded.
- `scripts/mutation_harness.py` `source_path` resolves a result class (`VFlipResult`, `AperiodicFitResult`)
to the package `__init__.py`, because the class keeps its old `__module__`. Check: a class resolves to
the file that defines it, or is refused by name. Waits: no caller names a class.
- `docs/04` carries release-transitional clauses. Check: the clauses cut. Waits: direction right everywhere.
Accept: each check passes and the suite is green.
Stop: a change moves a documented value without a ruling.

### 10-04 Laminar edges and a laminar page

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-lfp-spectral. Blocked by: none.
Writes: `jnwb/laminar/**`, `scripts/calibrate_vflip.py`, `scripts/calibrate_xflip.py`, `tests/test_laminar.py`, `tests/test_xflip.py`, `tests/test_zflip*.py`, `docs/laminar.md`, `mkdocs.yml`.
- P-228: `vflip` shares its name with a different published procedure. Check: the choice of `artifacts/evidence/0.2.8/plan/decisions.md` D7. Waits: rename is a public API ruling.
- P-229: the vflip receipt hashes docstrings. Check: hash code without docstrings. Waits: fails closed.
- P-285: the xflip receipt hashes comments. Check: the same hash rule. Waits: fails closed.
- P-351: `vflip` reports `log(max(1e-12, metric))`, so no support reads as -27.63. Check: -inf or NaN with the reason. Waits: rejected at the 3.75 gate.
- P-353 vflip half: a caller threshold at or below -27.63 accepts a zero-support fit. Check: closed by P-351. Waits: the default is 3.75.
- Depth declaration guard: `vflip` accepts a non-monotone `depth_axis`. Check: a criterion Hamm rules (`artifacts/evidence/0.2.8/plan/decisions.md` D10), the staggered shaft as the test. Waits: what counts as a depth axis is a scientific choice.
- Zflip long ramps: one flat contact makes every pair unidentifiable; the zero-gradient guard is unreachable; the fewer-than-3-bins docs check runs at `n_surrogates=0`; long cumsum ramps exceed the ramp width. Check: untouched pairs draw their own nulls (IB-99's 0.2.8 note), the guard removed or tested, the docs check run with surrogates, a ramp rule that keeps the offset signal. Waits: at defaults the `min_wpli` gate and the pair test refuse first.
- Tie-width test reach, vflip part: `scripts/calibrate_vflip.py` hashes a single module. Check: the receipt walks every module the estimator reaches.
- Generator seeds and `jrsa` axes, laminar part: `xflip` and `zflip` record no seed for a `Generator`. Check: a child seed recorded.
- 06-97 residue: no topic page documents the laminar operations. Check: `docs/laminar.md` with one call site each for `vflip`, `xflip`, `zflip` and `label_layers`, on the nav.
Accept: each check passes; calibration records regenerated.
Stop: a criterion is a scientific choice with no ruling.

### 10-13 No dangling references in `jnwb/`

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 10-03, 10-04.
Writes: `jnwb/__init__.py`, `jnwb/compression.py`, `jnwb/spectral/**`, `jnwb/laminar/**`.
Split from 10-08, whose write set does not reach these files.
- P-296: dangling references in `jnwb/` (`nwb_tfr_storage_spec.md`, `artifacts/benchmarks/...`) and development-history comments. Check: none left, merged with IA-29. Waits: no behavioural effect.
Accept: each check passes.
Stop: a fix changes shipped values without a ruling.

### 10-05 `connectivity` and `jrsa` as packages

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: none.
Writes: `jnwb/connectivity.py`, `jnwb/connectivity/**`, `jnwb/jrsa.py`, `jnwb/jrsa/**`, `tests/test_connectivity.py`, `tests/test_jrsa*.py`.
Split per `artifacts/evidence/0.2.8/plan/restructure_plan.md` (a); `bin_spikes` and `as_trials` stay importable from
`jnwb.connectivity`. Pure moves.
Accept: `jnwb.__all__`, signatures and every lookup the old module allowed are identical; the full
suite and gate 19 pass.
Stop: a move changes a number.
Waits: layout only.

### 10-06 Directed and similarity estimator edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-05.
Writes: `jnwb/connectivity/**`, `jnwb/jrsa/**`, `jnwb/rsa.py`, `tests/test_connectivity.py`, `tests/test_jrsa*.py`, `tests/test_rsa.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md`.
- P-227: the PSI jackknife leaves out a segment, not an epoch; liberal under zero-lag mixing (0.0655). Check: an epoch-level jackknife. Waits: stated with IB-97; conservative under independence.
- P-264: with undefined bands PSI sums `net` over defined bands only. Check: the docstring says so, or undefined bands make `net` NaN. Waits: flagged by `ok_for_interpretation`.
- P-196: no test pins `psi_freqs` or `psi_per_freq[0]`. Check: both pinned. Waits: output correct.
- PSI segment count and conditional networks: the default `nperseg` leaves 7 segments; `directed_network` has no conditional mode. Check: a default of about 20 segments and a conditional mode, each ruled first (`artifacts/evidence/0.2.8/plan/decisions.md` D10). Waits: p valid, a warning fires.
- IB-45: an int `rng` gives every pair the same surrogate stream. Check: one scheme for both, recorded per pair. Waits: each pair's p stays valid.
- Directed estimator edges: `bias_corrected_*` values sit off zero under mixing; `directed_network(method="psi", jackknife=False)` returns an all-NaN `q_matrix` silently; the TE large-n excess has no pinned mechanism. Check: the docstring, a warning, a record by n. Waits: no p depends on them.
- Tie-width test reach, directed part: the substitution probes accept any error type with no `match`; the PSI width test pins a lower bound only; TE's net width keeps the plain sum. Check: each probe matches its selector's message. Waits: all ten probes raise their own refusal today.
- P-331 jrsa and Granger half: `jrsa` standardises detrend residue, and the Granger residual guard sees it. Check: stated tolerances. Waits: degenerate input.
- P-256 information half: two MI functions name `spike_mutual_information` in their errors. Check: each names itself. Waits: message quality.
- P-332 similarity part: `cka` and `rv` give 1e-33 on a constant pattern; `_phase_slope` says normal-approximation p where the code uses t; `jrsa(align='bogus')` accepted at equal lengths; `rdm` takes flat input. Check: exact values, the docstring, a refusal, a named refusal for `rdm`. Waits: degenerate or wording.
- IB-44: a calibrated block bootstrap for the `jrsa` paired metrics replaces the refusal (ruled 2026-09-25). Check: 95 % interval coverage near 0.95 on AR(1) pairs at phi 0.9. Waits: the refusal is correct.
- IB-48: `jrsa` accepts `device='cuda'` but never reaches the CuPy branch. Check: route it or drop the branch. Waits: records cpu truthfully.
- IB-58: the `jrsa` row-metric `window` at the default `adim` (integrator's 0.2.8 note, graded 70). Check: windowing the observation axis by default, with a CHANGELOG entry. Waits: stated in the docstring and page.
- `jrsa` resampling fallback: `_resample_axis` downsamples when SciPy is missing while `align` echoes the request. Check: the branch removed. Waits: SciPy is declared.
- Generator seeds and `jrsa` axes, similarity part: the `adim` refusal's dropped-axis branch has no test. Check: a test.
- P-281: `test_cuda_matches_cpu` for `jrsa` compares CPU with CPU. Check: renamed or removed. Waits: no GPU path.
Accept: each check passes; calibration records in `artifacts/evidence/0.2.10/`.
Stop: a default change without a ruling.

### 10-07 `statistics` as a package

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: none.
Writes: `jnwb/statistics.py`, `jnwb/statistics/**`, `tests/test_statistics.py`, `artifacts/frozen_validated.json`.
Split per `artifacts/evidence/0.2.8/plan/restructure_plan.md` (a); `StatisticalAnalysis` moves whole. Gate 19's two
`jnwb/statistics.py` entries are re-pointed with unchanged hashes.
- `tests/test_statistics.py:707` reads `inspect.getsource(jnwb.statistics)`, which on a package returns
only `__init__`, so the check passes vacuously after the split. Check: it scans every module of the
package, and a reintroduced key in a submodule fails it.
Accept: `jnwb.__all__`, signatures and every lookup the old module allowed are identical; the full
suite passes, and gate 19 passes with no hash changed.
Stop: a move changes a function body gate 19 hashes.
Waits: layout only.

### 10-08 Statistics, spiking and decoding edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per finding. Blocked by: 10-07.
Writes: `jnwb/statistics/**`, `jnwb/permutation.py`, `jnwb/spiking.py`, `jnwb/onset_fitting.py`, `jnwb/analyzers.py`, `jnwb/trajectory.py`, `jnwb/gpu_pca.py`, `jnwb/bilinear.py`, `jnwb/nam.py`, `jnwb/artifact_repair.py`, `jnwb/_spread.py`, `jnwb/_bins.py`, `jnwb/_dictlike.py`, `jnwb/paths.py`, `jnwb/testing/**`, `tests/test_statistics.py`, `tests/test_permutation.py`, `tests/test_spiking*.py`, `tests/test_analyzers*.py`, `tests/test_trajectory*.py`, `tests/test_bilinear*.py`, `tests/test_rng*.py`, `skills/jnwb-statistics/SKILL.md`, `skills/jnwb-spiking/SKILL.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`.
- P-265: one value per group gives NaN ANOVA beside `eta_squared` 1.0. Check: NaN or a stated reason. Waits: no p or flag passes.
- P-297: the `compare_multiple_groups` docstring omits NaN `eta_squared` for an empty group. Check: stated. Waits: loud NaN.
- P-321: `confirmatory_compare` returns `correction: "none"` beside BH q values. Check: the key names what it describes. Waits: q named separately.
- P-329: an arithmetic paired difference gives t near 6e15 rather than inf. Check: stated. Waits: outside the exact-equality rule.
- P-346: the sign-flip tie tolerance over-counts at 1e11 dynamic range, and no test pins its size. Check: a test pins 8 eps. Waits: conservative.
- P-350: `permutation_test` reports significant at the floor with NaN difference beyond 1.8e308. Check: NaN on non-finite centred values. Waits: no physical input.
- P-333: no test catches `is_constant(ignore_nan=True)` regressing. Check: a NaN case in a row with spread. Waits: verified correct.
- P-334: `_spread.zscore` on inf returns `[-inf, -inf, nan]`. Check: NaN. Waits: non-finite input only.
- P-246: `paired_fire_prob_test(rng=<int>)` raises `AttributeError`. Check: a checked `TypeError`. Waits: loud.
- P-255: `causal_exp_smooth(tau_ms=0)` returns NaN with a warning. Check: a refusal. Waits: loud NaN.
- P-256 permutation half: `build_permutation_plan(labels, None)` raises a bare `TypeError`. Check: it names `groups`. Waits: message quality.
- P-231: the Rayleigh comment quotes the second-order formula. Check: aligned. Waits: code correct.
- Deprecations to complete: the `autocorrelogram` refractory verdict values (`jnwb/analyzers.py`) are removed, and trajectory `explained_variance` carries the per-component values (`jnwb/trajectory.py`), as their 0.2.7 warnings say. Check: both land with a CHANGELOG entry. Waits: ruled to land one release after the warning, as the spectral one in 10-03.
- P-315: `_whole_bin_count` prints "Use , or ..." for a reversed window, and its tolerance near 3e7 bins was not rechecked. Check: the message and a test. Waits: loud on unrealistic input.
- P-320: the whole-bin refusal prints refused and suggested windows alike at large times. Check: enough digits. Waits: error path only.
- P-319: the refractory-key test accepts any number of warnings. Check: exactly one. Waits: one in 60 of 60.
- P-292: after `cupy.linalg`, `compute_population_trajectory(device='cuda')` warns the wrong cause. Check: the message names the DLL conflict. Waits: `device_used` correct.
- P-323: `compute_population_trajectory` omits `device_used` for an empty area. Check: always present. Waits: nothing computed.
- P-343: float32 PCA with a near-degenerate top pair differs across devices. Check: parity below working precision declared undefined. Waits: below working precision.
- P-332 remainder: flat input in `fit_exponential_onset` and `population_trajectory`; the `UnitAnalyzer` multi-class error; project-history text in `nam.py` and `bilinear.py`. Check: named refusals, text removed. Waits: loud or wording.
- Response-significance wording: the bursting limit holds for 4 ms bursts and falls to 19 % at 50 ms, unstated in four homes; `RenamedKeyDict.setdefault` inserts a shadow key. Check: the limit stated once and linked, `setdefault` fixed. Waits: direction right everywhere.
- RNG surface: the dataset builders annotate `seed: int`, and the stochastic-parameter walk finds only `rng` or `seed`. Check: annotations and a walk by `resolve_rng` use. Waits: annotation only.
- IA-19: two-class `bilinear` `predict_proba` is overconfident (0.856 predicted, 0.582 observed). Check: one model for two classes and a calibration test. Waits: experimental and outside `__all__`.
- IA-23: `bootstrap_ci` loops in Python (11x slower at n 200). Check: vectorised with a version note, since the random stream changes (graded keep 2026-09-25). Waits: same order.
- IA-28: `bilinear` tests check a length only. Check: value-pinning tests with IA-19. Waits: goes with IA-19.
- IA-29: `nam` cites missing scripts and calls `torch.manual_seed`; `REWARD_WINDOW_MS` is unused; `artifact_repair` cites two missing scripts; `layer_masks_path` hardcodes project folders. Check: a local `torch.Generator`, the leftovers removed. Waits: non-exported modules.
- P-216 statistics part: the unscoped-delay paraphrase branch is unpinned. Check: a killing test. Waits: behaves correctly.
- P-280 remainder: the shared note at `jnwb/statistics.py:782` says "as selected by test=", which `correlate` (it takes `method=`) emits at `:1127`; `population_trajectory` passes a short context name (`context='population_trajectory'` in `jnwb/analyzers.py`). Check: the note names the argument its caller takes, the context name is the qualified one. Waits: message wording.
- Closure pass 2026-10-05: the `quality_metrics` docstring (`jnwb/analyzers.py:566`) says a spike at the train's end counts, but with a duration that is not a whole number of seconds it falls outside the last whole bin (spikes 0, 0.5, 1.2, 2.5 give counts 2, 1 and Fano 0.333). Check: the docstring states the whole-bin rule, or the count includes it. Waits: wording; the value follows the stated bins.
- Closure pass 2026-10-05: the `quality_metrics` refractory comparison uses `<` with no tolerance, where `refractory_contamination` allows 1 ns; predates 0.2.9. Check: one comparison rule, called, not retyped (`AGENTS.md` 4.7). Waits: differs only for intervals within 1 ns of the period.
Accept: each check passes; values that move carry a CHANGELOG entry.
Stop: a fix changes shipped values without a ruling.

# 0.2.11

Theme: interpretation, routing and documentation hold: every interpretational pitfall has a
synthetic test, every skill points to its sources and composes with the router, displays and
documented call shapes are checked, and the identity and scientific-choice facts are held.

Acceptance: `AGENTS.md` §11; the facts 10-10 and 09-04 hold use the ruled lexicons; the router
composes the minimal skill set for each chain 07-09 tests; each published unit measure is a public
operation by its published definition or a ruled exclusion.

Every item here carries `deferred-0.2.10`, the deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.9 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| Y identity facts | 10-10, 09-04 | `jnwb/__init__.py`, `jnwb/compression.py`, `jnwb/_declarations.py`, the fact gate and its test, `artifacts/fact_stack.md` holder cells |
| G pitfalls and skill sources | 10-11, 10-12 | `tests/test_connectivity_pitfalls.py`, `tests/test_substitution_class_sweep.py`, `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-population/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`, `docs/03_representational_similarity_jrsa.md`, `docs/08_directed_connectivity_and_information.md` |
| D display, documentation and unit measures | 10-09, 10-14, 10-15 | `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `jnwb/unit_quality.py`, their tests, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `skills/jnwb-qc/SKILL.md`, `docs/vis.md`, `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`, `artifacts/evidence/0.2.9/unit_qc_inventory.md` |
| P skills composition | 07-08, 07-09 | `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`, `tests/test_composition_*.py` |

Question round at the opening: the B3 choice-name lexicon (10-10) and the dB-lexicon values 09-04
reads.

### 10-10 Identity and scientific-choice facts held

Release: deferred-0.2.10.
AUTONOMY: none for the B3 lexicon values; holder cells under the standing authorization of 2026-09-29; the rest is `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `jnwb/_declarations.py`, `artifacts/fact_stack.md`.
- I1 declared signature types for every numeric public operation, and type-checked composition edges. Check: a spikes-to-LFP-only edge, planted, is VIOLATED.
- B3 lexicon and exceptions table. Check: a planted defaulted `window=` with no cited reason is VIOLATED.
Accept: the Identity table and B3 report no UNHELD fact.
Stop: a declaration would change a public signature without a ruling.

### 09-04 Science and Skills facts held

Release: deferred-0.2.10.
AUTONOMY: none for the dB-lexicon values; holder cells under the standing authorization of 2026-09-29; the scans are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- S8 claim classes and the text check over docs, skills, figure labels and docstrings. Check: the 0.2.7 fig09 unit, planted, is VIOLATED.
- S1, S2, S5 and S7 scans as ruled in Q13. Check: each catches its planted case.
- K1 partition with k = 3 exclusive operations per shipped domain skill. Check: a two-operation planted skill is VIOLATED.
- Planned skills, moved from the fact stack as plan (Q14): the planned set is twelve, the ten of 0.2.6 with `jnwb-landmark-viz` included (ruled 2026-09-22, P-180), plus `jnwb-paradigm` (experiment and timing semantics) and `jnwb-qc` (independent scientific and output QC); `jnwb-data-engineering` and `jnwb-compute` are gated on their public APIs and neither is a required endpoint: if the router can route a capability cleanly, no skill is manufactured for it. Check: each planned skill is created only when K1 and K5 hold for it.
Accept: the Science and Skills tables report no UNHELD fact.
Stop: a scan would need a scientific criterion not ruled in Q12 or Q13.

### 10-11 One synthetic test per interpretational pitfall

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-06.
Writes: `tests/test_connectivity_pitfalls.py`.
Source: table 2 of `artifacts/evidence/0.2.9/references/bastos_survey.md`. Each test builds the case it is named after, with a stated ground truth and an explicit `rng`.
- Common reference: a shared reference inflates coherence and Granger; `bipolar_reference` removes the inflation. Check: both directions asserted.
- Volume conduction: zero-lag mixing keeps `imaginary_coherency` and `wpli` near zero while coherence is high. Check: the bound is stated.
- SNR asymmetry: added noise on one channel yields a Granger direction with no true lag. Check: the test records today's behaviour and names the gap 11-04 closes.
- Common input: a common driver with unequal delays makes bivariate Granger spurious and conditional `granger` removes it. Check: both asserted.
- Sample-size bias: the `pairwise_phase_consistency` and debiased wPLI null means stay near zero for every segment count. Check: several counts.
Waits: tests only; each records present behaviour.
Accept: every pitfall statement of the `common_mistakes` pitfalls section is held by a test or names its gap.
Stop: a test would need a threshold no reference fixes.

### 10-12 Skills point to their sources

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per skill. Blocked by: 10-03, 10-06.
Writes: `skills/jnwb-connectivity/SKILL.md`, `skills/jnwb-lfp-spectral/SKILL.md`, `tests/test_skills_validation.py`.
- Each connectivity and spectral safeguard names its `docs/references.md` row instead of restating the method. Check: the line test finds no restated definition. Waits: pointers only.
- A request to compare with published nonparametric Granger values meets the estimator difference, as a decline or a qualification. Check: a decline-behaviour case. Waits: skill text only.
Accept: routing rows still match signatures; the summed skill length does not grow.
Stop: a pointer would drop a safeguard's dimension that a routing row needs.

### 10-09 Display edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-landmark-viz. Blocked by: none.
Writes: `jnwb/viz.py`, `jnwb/vis/**`, `jnwb/visual_qc.py`, `tests/test_vis*.py`, `tests/test_visual_qc.py`, `tests/test_viz*.py`, `skills/jnwb-landmark-viz/SKILL.md`, `skills/jnwb-figures/SKILL.md`, `docs/vis.md`.
- P-244: `apply_tight_auto_axis` floors y at 0, so signed data is drawn outside the axes. Check: a floor only for non-negative data. Waits: display only, stated.
- P-313: the stability panel coerces with `astype(bool)`, so a text flag plots every unit Stable. Check: a refusal of non-boolean flags. Waits: display only.
- P-275: the no-default-landmark test misses a `UnaryOp` default and a body fallback. Check: both fixtures. Waits: the code has neither.
- Vis label edges: a full label in `plot_csd`'s `colorbar_title` doubles the unit; a whitespace title; the depth hover has no unit. Check: a title naming a unit refused, the hover names `depth_unit`. Waits: visibly contradictory, never silent.
- Vis range edges: the hierarchy hover's "%" removal is unpinned; `plot_spectrolaminar_map` draws infinities as gaps; an empty `rel_power` fails in numpy. Check: a killing assertion, infinities refused, a named error. Waits: shipped hover correct.
- P-254: `Canvas.save_and_seal` loses its export on a loaded Windows machine when choreographer's shutdown budget expires; a serial run can hang at exit after a failed close; no test shows an export error reaching the caller. Check: one kaleido session per call, a serial run exits after a failed close, the swallowed-error mutant killed, later calls fail fast. Waits: loud. Observed 2026-10-04 under xdist too: on a loaded machine a `-n 12` run of `4be1792b` hung 17 minutes in a headless Chrome child of one worker, and after that child was killed the suite reported 0 failed, so a lost export did not reach the test that made it. Whether that can make qualifying evidence falsely pass is for the closure pass to classify.
- P-280 ribbon: `docs/vis.md:73` and the `jnwb/vis/state_space.py:34` docstring promise a ribbon that `plot_decoding_timecourse` draws only when `ci_low` and `ci_high` are given. Check: both say so. Waits: wording.
- P-367: no test pins the `raster_psth` SEM value; a ddof=0 mutant and a mutant that drops the division by the square root of the trial count both pass all 423 tests in the 11 files that call it (found 2026-10-04 at `94334cb4`). Check: a hand-computed SEM kills both. Waits: display helper, value unchanged.
- P-332 display part: `plot_sorted_heatmap(category_labels)` is ignored. Check: used or refused. Waits: display.
- P-216 display part: the gradients crossover default and the `jnwb.vis` vocabulary beyond a grep are unpinned. Check: killing tests. Waits: behaves correctly.
- Closure pass 2026-10-05: `plot_unit_waveforms(channels="peak")` takes the largest absolute deflection while `waveform_features` takes the largest max minus min, so the drawn and the reported peak channel can differ. Check: both call one peak-channel rule (`AGENTS.md` 4.7). Waits: display only; the reported features are unchanged.
Accept: each check passes.
Stop: none beyond the standing ones.

### 10-14 A type oracle for documented call shapes

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `tests/test_docs_call_shapes.py`, `scripts/docs_form_gate.py`, `tests/test_skill_symbol_coverage.py`.
Split from the documentation-check item on 2026-10-04, which landed every other bullet.
- P-167 and P-84: P-79b, P-79c and P-82 are wrong-type calls that bind cleanly; the recorded call fragments use names the page never assigns (`lfp_segments`, `spike_trains`, `session_qc_list`). Ruled 2026-10-04 (Hamm): an annotation oracle over literals and page-assigned names, plus a small table of argument types for names a page never assigns. Check: the oracle fails all three. Waits: the documented calls are already corrected; the oracle guards recurrence.
- The nav reader `_nav_pages` of `tests/test_skill_symbol_coverage.py` reads commented `mkdocs.yml` lines as pages. Check: it calls the gate's nav reader. Waits: no commented page exists.
Accept: each check passes.
Stop: the oracle needs a type that no annotation or table entry states.

### 10-15 Four published unit measures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: none.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/unit_quality.py`, `tests/test_unit_quality.py`, `skills/jnwb-qc/SKILL.md`.
Moved from the 0.2.9 inventory on 2026-10-04 (ruled). The code read was `E:/omission` at `c3d69375`, which copies the duration measure and the unit screen of the lab pipeline it cites (`yihan777/alpha_beta_mechanism@826e540`).
- Four published measures the copied screen applies and jnwb lacks: amplitude cut-off (Hill et al. 2011), half-width, repolarisation slope and spread (Jia et al. 2019). Check: each a public operation by its published definition, or a ruled exclusion. Waits: new capability, not a defect.
- Closure pass 2026-10-05: `refractory_contamination` says the Hill et al. (2011) derivation "is restated by Llobet et al. (2022)"; Llobet's model differs from Hill's and the sentence was not checked against the paper. Check: the sentence matches the paper, or is removed. Waits: citation wording; the computation follows Hill.
Accept: each check passes.
Stop: a new public operation, or a definition with more than one published form, needs Hamm's ruling.

### 07-08 The router composes the minimal skill set a task needs

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb. Blocked by: none.
Writes: `skills/jnwb/SKILL.md`, `skills/jnwb/agents/openai.yaml`, `tests/test_skill_router_reach.py`.
Router section 2 maps each task phrase to one skill, so a multi-skill task reaches the first match.
Accept: a table of tasks and required skill sets passes, with plotting supplied arrays reaching
figures and QC, and a band comparison between conditions reaching paradigm, NWB data, spectral,
statistics, figures and QC.
Stop: a task needs a skill outside the fact stack's planned set.
Waits: router feature; no shipped behaviour changes.

### 07-09 Composition tests over the chains the router sequences

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per chain. Blocked by: 07-08.
Writes: `tests/test_composition_*.py`.
No test composes two skills' operations in router order where each call is right and the order,
an identifier or a substituted signal class is wrong. Minimal base: the band-comparison task as one
chain.
Accept: each chain runs on unequal dimensions, fails on the wrong composition and passes on the
right one; a chain correct today records its killing mutation in its docstring.
Stop: a chain is wrong today and its repair needs a path outside `Writes`.
Waits: new tests of new composition.

# 0.2.12

Theme: the release apparatus is smaller and faster, and the repository carries no process
identifiers outside the stacks.

Acceptance: `AGENTS.md` §11; `scripts/` and the process tests are shorter than at `fe14858d` with
every gate still reported; no item or problem id outside `artifacts/` except machine-required
literals.

Every item here carries `deferred-0.2.10`, the deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.9 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| M gates | 12-09, 12-01 | `scripts/harness_gate.py` and its split, `scripts/stack_parse.py`, `scripts/stack_edit.py`, gate and stack tests |
| L release and CI | 12-02, 12-03, 12-05 | `scripts/release_gate.py`, `scripts/smoke_installed.py`, `scripts/measure_peak_memory.py`, the workflow, `CONTRIBUTING.md`, release tests, the process tests on the prune list, `scripts/measure_agents_md_duplication.py`, `scripts/reconstruct_state.py` |
| N mutation and references | 12-04, 12-08 | `scripts/mutation_harness.py`, `scripts/computational_contract_gate.py`, their tests, `scripts/build_fact_graph.py`, the fact gate test, `artifacts/fact_stack.md` |
| Z alone | 09-07, 12-07, 12-06 | the workflow, the harness and fact gates, their tests, `scripts/learning_gate.py`, `scripts/reconstruct_state.py`, `tests/test_learning_gate.py`, `tests/test_state_reconstruction.py`, `artifacts/defect_classes.md`, and every comment in `scripts/` and `tests/`; runs when no other lane is open |

12-02 starts once 12-09 is merged. Question round at the opening: the study-vocabulary values and
the 12-08 row wording.

### 12-09 One stack parser

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/stack_parse.py`, `scripts/stack_edit.py`, `scripts/harness_gate.py`, `tests/test_stack_metadata_contradictions.py`, `tests/test_stack_edit.py`.
- P-232: gates 15 and 17 read only `###` items while STEP 0a reads any depth. Check: one parser in `scripts/stack_parse.py`, used by both. Waits: the gates can only under-read.
- P-274: STEP 0a leaves four HTML heading forms unparsed. Check: the shared parser reads them. Waits: no HTML headings.
- Stack editor edges: `os.replace` raised WinError 5 once under load; no chained-edit test; a fence line can be removed; heading depth capped at six where the gate takes any; non-breaking-space indents; the check-then-replace race and missing fsync. Check: a retry, the chain test, a fence check, one heading rule. Waits: one call per edit reaches none of these.
Accept: gates 15 and 17 read `scripts/stack_parse.py` and pass; the stack tests pass.
Stop: the parser changes gate 15's or 17's verdict on any fixture.

### 12-01 Gates in their own modules

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-09.
Writes: `scripts/harness_gate.py`, `scripts/gates/**`, `tests/test_harness_adversarial_gates.py`, `tests/test_every_gate_runs.py`, `tests/test_gate*.py`, `tests/test_gates_reject_the_trees_they_passed.py`.
Plan: `artifacts/evidence/0.2.8/plan/restructure_plan.md` (a), scripts row.
- P-218: gate 2 excuses a counterfeit at a stale worktree registration. Check: the admin `gitdir` points back. Waits: needs a counterfeit.
- P-219: gate 2's PASS message is narrower than its check. Check: the message. Waits: no verdict changes.
- P-235: the stated-gate-count test misses `skills/`, `docs/`, number words and ranges. Check: all read. Waits: the live count is correct.
- P-295: gate 14's id pattern passes `items/06-55`, `P-1000`, `p-29` and fails `09-23`. Check: the pattern. Waits: live tree clean.
- P-311: gate 14 does not read `README.md` or follow `--8<--` includes. Check: both. Waits: clean at `3f533574`.
- P-301: no test pins the removal of an external project's name from `jnwb/vis/sidecar.py`. Check: gate 6's token list. Waits: clean.
- P-342: gate 19 hashes a name's first definition only and accepts a wrongly-named killing test. Check: last binding hashed, test ids resolved. Waits: no name bound twice.
- P-198: `run_full_preflight` de-duplication is unpinned. Check: a killing test. Waits: a duplicate cannot hide a failure.
- P-304: gate 9's api sync is untested against a same-length drift, the contract gate against a doubly-categorised export, and `win_ms=` literals against `bin_ms`. Check: a fixture each. Waits: no evidence passes falsely.
- P-216 gate part: a second interpreter sentence (gate 8 reads the first) and `sys.modules.clear()` in the collection-order detector are unpinned. Check: killing tests. Waits: behave correctly.
Accept: `python scripts/harness_gate.py` reports every gate PASS; the gate tests pass; the harness
is shorter.
Stop: a split changes a gate's verdict on any fixture.

### 12-02 The release gate reads the shared parser

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-09.
Writes: `scripts/release_gate.py`, `tests/test_release_requires_an_empty_problem_stack.py`, `tests/test_release_body_gate.py`, `tests/test_release_recovery_gates.py`, `tests/test_release_version_is_unpublished.py`, `tests/test_generation_closure_is_declared.py`.
- P-300: the STEP 0a message truncates item titles. Check: whole titles. Waits: wording only.
- P-302: a problem-shaped row outside `## Open` is not counted. Check: counted. Waits: Open is fully checked.
- P-330: renaming a required id to a deferred one after the receipt reads as one done and one added. Check: no new ids after the receipt. Waits: needs a deliberate rename.
- Readiness blind spots: a `##` section listing work outside any item; `--assume-unchanged` and `--skip-worktree` files; a job-level `continue-on-error` on TestPyPI. Check: each refused. Waits: none present.
- RP-2: STEP 0e refused on an in-progress pull-request run while the push run for the commit passed. Check: a concluded green run for the exact commit suffices, tested. Waits: fails closed.
Accept: STEP 0a imports `scripts/stack_parse.py`; its tests pass.
Stop: the shared parser reads an item STEP 0a did not, or the reverse, on the live stack.

### 12-03 CI and release workflow

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-02.
Writes: `.github/workflows/workflow.yml`, `scripts/smoke_installed.py`, `scripts/measure_peak_memory.py`, `CONTRIBUTING.md`, `tests/test_workflow_release_policy.py`, `tests/test_ci_conclusion_gate.py`, `tests/test_import_provenance.py`, `tests/test_distribution_manifest_inspection.py`, `tests/test_dependency_floors_are_installable.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_test_imports_survive_the_wheel_leg.py`.
- RP-7: a threshold on peak memory beside wall time in the suite step. Check: set from the recorded measurements. Waits: needs the 0.2.7 measurements first.
- CI guard hardening: exit-masking forms in the pytest steps, `set +e` in Resolve, a re-upgrade after the constrained install, only `env.FLOOR_PYTHON` checked, two copies of the browser retry. Check: each refused by a test. Waits: each needs a deliberate workflow edit.
- Peak-memory reset evidence: a clear_refs write counts as a reset unobserved; the unwritable case is undocumented; the `ru_maxrss` fallback is unlabelled. Check: a re-read, a row, a label. Waits: every row is labelled correctly.
- Floor coverage: 3.12.0 runs only on the Ubuntu floors leg. Check: newest dependencies on 3.12.0, and Windows 3.12.0. Waits: the known defect class reaches the Ubuntu leg.
- One smoke definition: CI's smoke script and the release gate's installed-package script check different things. Check: one definition both run. Waits: each exercised where it runs.
- P-352: the release gate's smoke script runs only at step 7. Check: the suite runs it against the tree. Waits: fails closed.
- P-353 smoke half: the smoke step keeps `PYTHONPATH` where the tutorial step strips it. Check: stripped. Waits: asserts a `site-packages` import.
- Release workflow edges: the smoke pass branch, export and extra checks are untested to failure; a yanked TestPyPI file passes the hash comparison; the verify job's one-wheel count is not asserted. Check: tests. Waits: each fails loudly in CI.
- P-309: the distribution tests read only `<repo>/dist` and do not reject `examples` or `data` components. Check: an external build path and the rejection. Waits: the byte comparison held.
- P-328: Actions pinned to tags. Check: commit SHAs, then the requirement on. Waits: GitHub-owned and allow-listed.
- P-191: a contributor install without `vis` fails the `__all__` sweeps. Check: those tests skip names of absent extras. Waits: false failures only.
- P-197: the provenance scanners miss ten spellings and accept five prepend forms. Check: each a fixture, or the installed-wheel leg named as the check. Waits: the wheel leg catches a checkout-pinned test.
- Prepend scanner reach: slice assignment, rebinding, aliasing and non-zero indices are missed; the path-order assertion runs only when ordered after. Check: each flagged; the assertion at session end. Waits: no such form exists.
Accept: each check passes; one CI run on `dev` is green.
Stop: a hardening would refuse the current workflow.

### 12-04 Mutation and contract gate reach

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/mutation_harness.py`, `scripts/computational_contract_gate.py`, `tests/test_mutation_harness_validity.py`, `tests/test_computational_contract_gate.py`, `tests/test_substitution_class_sweep.py`.
- P-238: `collect_selector` drops node ids containing a space. Check: such ids selectable. Waits: fails closed.
- P-266: the contract gate tracks aliases without order and accepts one correct path among several. Check: order-aware aliasing. Waits: switch tests hold live behaviour.
Accept: each check passes.
Stop: none beyond the standing ones.

### 12-05 Process tests pruned and merged

Release: deferred-0.2.10.
Ruled 2026-09-29 (D12): the list is accepted, run after the gates split.
Role: jnwb-developer. Skill: none. Blocked by: 12-01.
Writes: `artifacts/evidence/0.2.12/process_tests/**`, `tests/test_findings_ledger.py`, `tests/test_single_agent_instruction_file.py`, `tests/test_standing_rules_name_no_cycle.py`, `tests/test_agents_md_stays_a_router.py`, `scripts/measure_agents_md_duplication.py`, `tests/test_release_recovery_gates.py`, `tests/test_jrsa.py`, `tests/test_api_md_is_interpreter_independent.py`, `tests/test_workflow_release_policy.py`, `tests/test_state_reconstruction.py`, `tests/test_state_basis_is_checked.py`, `tests/test_xflip_calibration_receipt.py`, `tests/test_vflip_calibration_receipt.py`, `tests/test_test_imports_survive_the_wheel_leg.py`, `tests/test_the_suite_can_qualify_an_installed_copy.py`, `tests/test_errors_documented.py`, `tests/test_readme_smoke.py`, `scripts/reconstruct_state.py`.
The files are the ruled list, resolved against `artifacts/evidence/0.2.7/process_test_audit.md`.
- Process tests to prune or merge: 4 files to prune, 4 to merge, and four weaker checks a stronger test covers. Check: each pruned case is shown held by a stronger test first.
- P-290: the ruled test taxonomy (`CONTRIBUTING.md:154`) is enforced by nothing. Check: each kept process test named under one category in the prune record; a taxonomy change goes to 12-06, which owns `CONTRIBUTING.md`.
- Apparatus bound: `artifacts/goal.md` §10 has no check. Check: `scripts/reconstruct_state.py` records the line counts of `scripts/` and the process tests, so growth is visible per release; a refusal is a new item's to add if Hamm asks.
Accept: the pruned files' cases are held by the stronger tests named in the audit.
Stop: a pruned test is the only one that kills some mutant.

### 12-06 No process identifiers outside the stacks

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 12-01, 12-02, 12-03, 12-04, 12-05, 12-07, 12-08, 12-09.
Writes: `scripts/*.py`, `tests/**/*.py`, `.github/workflows/workflow.yml`, `CONTRIBUTING.md`.
- P-284: 134 identifiers in 7 `scripts/` files and 641 in 98 test files cite item and problem ids (P-209 and IB-71 merged here). Check: each removed or rewritten as a plain reason, then gate 14 extended to both folders with an allowlist for machine-required literals.
- P-102: line endings levelled across the tree if `artifacts/evidence/0.2.8/plan/decisions.md` D3 rules it, as the last commit of the cycle, since it touches every file. Check: gate 16 passes and one byte-mode edit per convention applies.
Accept: gate 14 passes on `scripts/` and `tests/`; the suite passes.
Stop: an id is a literal a parser fixture needs.
Waits: neither directory ships.

### 12-07 Release and study-vocabulary facts held; no fact UNHELD

Release: deferred-0.2.10.
AUTONOMY: none for the study-vocabulary values; holder cells under the standing authorization of 2026-09-29; the rest is `max`.
Role: jnwb-developer. Skill: none. Blocked by: 12-01, 12-03, 12-05, 12-08.
Writes: `.github/workflows/workflow.yml`, `scripts/harness_gate.py`, `scripts/gates/**`, `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `tests/test_harness_gate_study_tokens.py`, `artifacts/fact_stack.md`.
- R2: a verify-pypi job after publish-pypi (fresh install from PyPI, sha256 equal to the tag run's artifact, `pip check`, the installed smoke test). Check: a planted hash mismatch fails the job's check function.
- B2: Gate 6 scans all of `jnwb/`, `docs/`, `skills/` and `tests/`; each hit repaired or shown generic. Check: a planted study token in `tests/` fails.
Accept: `scripts/fact_gate.py` prints UNHELD 0 and VIOLATED 0.
Stop: a workflow change would alter the ruled publication order.

### 12-08 Every routed method cites a published source

Release: deferred-0.2.10.
AUTONOMY: none for the fact row; the graph edges are `max`.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/build_fact_graph.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- The fact graph gains reference nodes and DOI-to-function edges read from `docs/references.md`. Check: a planted row with no function is reported.
- A proposed Science fact, every routed method cites a published source, held by `tests/test_references_resolve.py`. Check: Hamm approves the row; it reads HELD.
Accept: the fact gate reports the row HELD, or it waits with Hamm's reason.
Stop: the fact stack is Hamm's; the row lands only on approval.

### 09-07 Checks for the defect classes review keeps finding

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: none.
Writes: `scripts/learning_gate.py`, `scripts/reconstruct_state.py`, `scripts/harness_gate.py`, `tests/test_learning_gate.py`, `tests/test_state_reconstruction.py`, `artifacts/defect_classes.md`.
Source: `artifacts/defect_classes.md`; each bullet is a class seen twice, or one whose check is cheap.
- ruling-cited-not-recorded: a "Ruled <date>" citation in `artifacts/` names a ruling its dated file lacks. Check: a gate reads every such citation and finds its row in `artifacts/rulings/<date>.md`, red on the 08-06 commit `8482c7bc`. Waits: process evidence only; no shipped behaviour.
- rewrite-drops-obligation: a rule-file rewrite loses an obligation its mapping calls kept. Check: for a mapping table with old and new columns, every obligation word (`before`, `after`, `never`, `must`, `only`) in an old rule appears in its new home, red on `8482c7bc` for D1 and D2. Waits: rule-file rewrites are rare and reviewed.
- second-home-contradiction: a ruled rule keeps its old form in another file. Check: each ruling row may name a forbidden phrase, and the gate greps the repository for it, red on the pooling phrase before 08-07. Waits: every instance so far was found by review.
- Awareness in state: `artifacts/state.md` records the live worktrees and branches with their HEADs, the newest `CI/CD` run on `dev` with its conclusion, and the open defect classes. Check: the section is generated, and a stale worktree or a red run is named. Waits: the integrator reads these by hand today.
- The ledger is counted, not typed: `artifacts/defect_classes.md` `Seen` equals its instances. Check: the gate recounts. Waits: hand-kept today.
Accept: each check is red on the instance its bullet names and green on the live tree; the harness counts the new gate.
Stop: a check needs judgement a script cannot make; it stays a review rule instead.

# 0.2.13

Theme: NWB reading and writing are complete: every container `inspect` lists is readable, and the
mutation and execution APIs ship in the shape Hamm rules.

Acceptance: `AGENTS.md` §11; 07-21 and 07-22 ship only in the ruled shape; each landed writer has a
re-read test and an ambiguity refusal.

Every item here carries `deferred-0.2.10`, the deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.9 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| I reading | 11-01 | `artifacts/evidence/0.2.11/**`, `jnwb/nwb_inspect.py`, `jnwb/nwb_io.py`, `jnwb/nwb_events.py`, `jnwb/io.py`, `jnwb/mcp_server/**`, their tests, `docs/errors.md`, `skills/jnwb-nwb-data/SKILL.md` |
| J files and tables | 11-02, 07-05 | `jnwb/compression.py`, `jnwb/metadata.py`, `jnwb/addressing.py`, `jnwb/ontology.py`, `jnwb/paths.py`, their tests, `docs/02_paths_addressing_metadata.md`, `skills/jnwb/SKILL.md`, `CONTRIBUTING.md` |
| K new APIs | 11-05, 07-21, 07-22, 11-03 | `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `mkdocs.yml`, new modules, their tests and pages, the fact gate and its test, `artifacts/fact_stack.md` holder cells |

Question round at the opening: the mutation set (07-21) and the execution and cache surface
(07-22) from 08-08's proposal.

### 11-01 Every container `inspect` lists is readable

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/nwb_inspect.py`, `jnwb/nwb_io.py`, `jnwb/nwb_events.py`, `jnwb/io.py`, `jnwb/mcp_server/**`, `tests/test_nwb_inspect.py`, `tests/test_nwb_read_tolerance_and_visibility.py`, `tests/test_nwb_events.py`, `tests/test_mcp_server.py`, `tests/test_io*.py`, `docs/errors.md`, `skills/jnwb-nwb-data/SKILL.md`.
- P-294: `acquisition_channel` does not resolve behavior containers under `processing/`. Check: `processing/behavior/EyeTracking` reads. Waits: loud.
- P-314: `BehavioralEvents` cannot be read by any name; `BehavioralEpochs` and ophys unprobed. Check: one table covers every container `inspect` reports. Waits: loud; same root as P-294.
- P-303: `inspect` of an in-memory file and the file walk unwrap different container sets. Check: one unwrap rule. Waits: known types agree.
- P-299: `inspect` reports `packaging` `direct` for wrapped containers with nested `data_path`. Check: the right label. Waits: vocabulary only.
- P-190: a series with `timestamps` and no constant `rate` raises `AcquisitionNotFoundError`. Check: the exception class of `artifacts/evidence/0.2.8/plan/decisions.md` D8. Waits: message true; a new class is API.
- P-204: `ContainerTypeContradictionWarning` blames the type when only the `uV` unit is wrong (78 of 96 corpus warnings). Check: a unit-scale message distinct from a type message (D8). Waits: errs toward caution.
- P-220: an empty `session_description` group raises `ValueError` under the waiver. Check: a missingness-table row and a named error. Waits: fails loudly.
- P-336: no test pins the `channel_conversion` length refusal. Check: a killing test. Waits: behaves correctly.
- P-337: the unit warning names only `conversion=`, and the `starting_time` warning points at `nwb_inspect.py`. Check: both conversions named, `stacklevel` at the caller. Waits: messages true.
- P-216 reading part: the `/acquisition` bare-name ambiguity refusal is unpinned. Check: a killing test. Waits: behaves correctly.
- MCP signal reference edges: the reader check does not pin the channel axis; a `channel_conversion` outside the schema is reported but ignored; an infinite rate is accepted; the sweep row omits the reference tool's handler. Check: each a test or a refusal. Waits: loud or outside the schema.
- P-289: the MCP writes-nothing test snapshots two directories, and the no-`jnwb.testing` check misses `importlib`. Check: a whole-tree snapshot and a runtime check. Waits: no current path does either.
- P-291: `stream_npz_array` accepts `Ellipsis` on 0-d where its docstring says `TypeError`. Check: the docstring. Waits: value right.
Accept: each check passes.
Stop: reading a container would need to infer its meaning.

### 11-02 Compression, unit tables and addressing edges

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/compression.py`, `jnwb/metadata.py`, `jnwb/addressing.py`, `tests/test_compression.py`, `tests/test_metadata.py`, `tests/test_addressing.py`, `docs/02_paths_addressing_metadata.md`.
- P-283: `_timestamps_fate` does arithmetic with `None` when `rate` is absent. Check: a named refusal. Waits: loud.
- P-298: a hard-linked timestamps array is neither collapsed nor refused. Check: links resolved by object id. Waits: receipt consistent.
- P-324: `compress_fp32(select=)` on a SoftLink writes an independent copy. Check: stated or refused. Waits: pinned.
- P-338: a second link can open a cast irregular timestamps array. Check: refused or recorded per link. Waits: opt-in, recorded.
- P-344: wall time rises 2.4x from 800 to 1600 series. Check: a measurement against HDF5 per-op cost. Waits: linear op count.
- P-348: relative soft-link resolution, the soft-linked `select=` message and CUDA constant-channel NaN are unpinned. Check: tests. Waits: observed correct.
- P-192: `enrich_units_dataframe` without `peak_channel_id` fills Unknown silently. Check: a warning and the prerequisite on the page (06-90). Waits: Unknown, not wrong.
- P-242: `unit_census_report` drops absent grouping columns silently. Check: a warning. Waits: documented filter.
- P-312: `compare_old_new_criteria` mishandles nullable `is_stable`. Check: nullable handled. Waits: not exported.
- P-322: `get_all_units_metadata(filter_quality=True)` without `quality` raises where the CHANGELOG says a warning. Check: the warning. Waits: loud.
- `classify_layer_from_depth` reads electrode z as depth with no declared shallow end. Check: D10's ruling. Waits: stated; a ruling.
- P-216 addressing part: `VISp6a/b` splits into a spurious area. Check: a test and a fix. Waits: no corpus here carries it.
Accept: each check passes.
Stop: a fix would name an area vocabulary.

### 07-05 A downstream paper agent can consume jnwb

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: per skill. Blocked by: 11-02.
Writes: `jnwb/ontology.py`, `jnwb/paths.py`, `tests/test_preflight*.py`, `tests/test_paths.py`, `tests/test_paths_identity.py`, `skills/jnwb/SKILL.md`, `CONTRIBUTING.md`.
Ruled 2026-09-25: the paper agent lives downstream; jnwb gains only what it cannot do without.
- a. A script scores decline accuracy from `jnwb.preflight` alone: outcome, reason and missing inputs as data.
- b. A result names its input's sha256 and object path, through `Provenance` or `Lineage` if they can carry it; IA-27's tests for `resolve_nwb_path`, `sha256_file` and `require` land here.
- c. `CONTRIBUTING.md` states the intake: a downstream miss classified as a jnwb defect enters the problem stack as a generic row with a synthetic discriminator.
- P-335: review the omission project's laminar curation pull request (ruled 2026-09-24) against the Boundary: composable parts, cited parameter defaults, micrometres, no project vocabulary.
Accept: a test per outcome in (a); a round trip in (b) by path and hash; gate 6 passes.
Stop: a study, paradigm or DANDI id in `jnwb/`, `skills/` or `docs/`.
Waits: new downstream capability.

### 11-05 `ContainerTypeContradictionWarning` exported

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
Ruled 2026-09-29 (D8 (a)): exported.
- P-221: `ContainerTypeContradictionWarning` is not exported. Check: exported. Waits: changes no value.
Accept: the name is in `jnwb.__all__`; gates 5 and 9 pass.
Stop: none beyond the standing ones.

### 07-21 A public NWB mutation API

Release: deferred-0.2.10.
AUTONOMY: none until Hamm rules the set from 08-08.
Role: jnwb-developer. Skill: jnwb-nwb-data. Blocked by: none.
Writes: `jnwb/nwb_write.py`, `tests/test_nwb_write.py`, `docs/writing_nwb.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
Accept: each landed operation re-reads its output and refuses an ambiguous mapping; API,
documentation and tests land before or with any skill.
Stop: anything that infers condition meaning, anatomy or units.
Waits: public API; Hamm rules the shape.

### 07-22 A public execution and cache API

Release: deferred-0.2.10.
AUTONOMY: none until Hamm rules the surface from 08-08.
Role: jnwb-developer. Skill: jnwb. Blocked by: 07-21.
Writes: `jnwb/execution.py`, `tests/test_execution_api.py`, `docs/execution.md`, `mkdocs.yml`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`.
Order, per the fact stack: numerical identity (08-08), then the public abstraction, then
performance evidence, then routing.
Accept: a cache key includes input hash, parameters and version, with an invalidation test; no
control changes a number.
Stop: a control would change a number.
Waits: public API; Hamm rules the surface.

### 11-03 Design facts held

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: none. Blocked by: 07-22.
Writes: `scripts/fact_gate.py`, `tests/test_fact_gate.py`, `artifacts/fact_stack.md`.
- D1 delegation edges for every public callable and each Analyzer method. Check: a planted two-step convenience is VIOLATED.
- D2 and D3 category tags on every operation with NWB or cache side effects, landing with 07-21 and 07-22. Check: an untagged planted writer is VIOLATED.
Accept: the Design table reports no UNHELD fact.
Stop: a category outside the ruled allowlists would be needed.

# 0.2.14

Theme: figures and tutorials, then the estimators and screens that wait on rulings or outside
inputs: the documentation shows its analyses as figures; the pitfall estimators are proposed and
land in the shapes Hamm rules; 13-04 waits for the collaborator's skill, 14-08 for access to the
lab pipeline, and 14-07 for a user who needs it.

Acceptance: `AGENTS.md` §11; every figure added follows the figure style ruled 2026-10-04, comes from
the docs generator in light and dark, and says in its caption whether it is synthetic; 13-04 and
14-07 land in the shape Hamm rules or are deleted.

Every item here carries `deferred-0.2.10`, the deferred value `scripts/release_gate.py` accepts
while the declared version is 0.2.9 (`artifacts/evidence/0.2.8/plan/decisions.md` D2).

## Lanes

| Lane | Items, in order | Owns |
|---|---|---|
| A figures and tutorials | 14-01, 14-02, 14-03, 14-04, 14-05 | `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/03_representational_similarity_jrsa.md`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`, `docs/05_artifact_detection_and_repair.md`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/common_mistakes.md`, `docs/tutorials/*.md`, `examples/tutorials/09_open_data.py`, `tests/test_synthetic_figures_are_labelled.py` |
| B estimators and screens | 11-04, 14-06, 13-04, 14-08 | `artifacts/evidence/0.2.11/pitfall_estimators_proposal.md`, `artifacts/evidence/0.2.9/unit_qc_inventory.md`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `jnwb/connectivity/**`, `jnwb/unit_quality.py`, their tests, `docs/references.md`, `docs/09_decoding_and_visual_qc.md`, `examples/unit_quality.ipynb`; `docs/08_directed_connectivity_and_information.md` and `docs/common_mistakes.md` once lane A has merged them |
| T trial correlation | 14-07 | `jnwb/spiking.py`, `tests/test_spiking.py`, `skills/jnwb-spiking/SKILL.md` |

Question round at the opening: the 11-04 shapes once its proposal exists, 13-04 against the
collaborator's skill, and whether any user needs 14-07.

### 14-01 Spectral and laminar figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/04_spectral_analysis_and_tfr.md`, `docs/coherence_and_tfr.md`, `docs/tutorials/06_laminar.md`.
Source: the "Top 10" list of the figure inventory of 2026-10-04, a read-only survey at `9cf0bb0f`,
numbered as there. Each figure is synthetic unless its bullet says otherwise, generated by
`docs/generate_figures.py` in the figure style ruled 2026-10-04 in light and dark, its caption naming each jnwb
function it calls.
- Inventory 10: the spectral page states Welch and multitaper PSDs in text only. Check: a figure of both with `CANONICAL_BANDS` shaded. Waits: documentation only; no number changes.
- Inventory 4: coherence, imaginary coherency and wPLI under zero-lag mixing are compared in text only. Check: a figure of the three on the coherence page. Waits: documentation only; no number changes.
- Inventory 6: the CSD and the vFLIP crossover have no figure. Check: CSD depth by time with the crossover (`current_source_density_1d`, `vflip_from_lfp`, `jnwb.testing.synth.synth_laminar_motif`, not `jnwb.vis.plot_csd`) on the spectral page and `docs/tutorials/06_laminar.md`. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-02 Spiking figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/06_spikes_psth_and_onset_dynamics.md`, `docs/common_mistakes.md`.
Source: the "Top 10" list of the figure inventory of 2026-10-04, a read-only survey at `9cf0bb0f`,
numbered as there. Each figure is synthetic unless its bullet says otherwise, generated by
`docs/generate_figures.py` in the figure style ruled 2026-10-04 in light and dark, its caption naming each jnwb
function it calls.
- Inventory 1: causal and Gaussian smoothing of a step differ by about 35 ms, stated in text only. Check: a figure of both (`causal_exp_smooth`, `gaussian_smooth_rate`, `fit_exponential_onset`) on the spiking page and in section 8 of `docs/common_mistakes.md`. Waits: documentation only; no number changes.
- Inventory 9: phase locking has no figure. Check: a spike-phase polar histogram with PLI and PPC on the spiking page. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-03 Inference and directed-connectivity figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/07_statistical_inference_and_nulls.md`, `docs/08_directed_connectivity_and_information.md`, `docs/common_mistakes.md`.
Source: the "Top 10" list of the figure inventory of 2026-10-04, a read-only survey at `9cf0bb0f`,
numbered as there. Each figure is synthetic unless its bullet says otherwise, generated by
`docs/generate_figures.py` in the figure style ruled 2026-10-04 in light and dark, its caption naming each jnwb
function it calls.
- Inventory 2: the cluster permutation test has no figure. Check: a TFR difference with the significant cluster outlined (`cluster_permutation_test`) on the inference page. Waits: documentation only; no number changes.
- Inventory 8: spectral Granger and the PSI trap are text only. Check: spectral Granger in both directions, and PSI narrowband against broadband, on the directed-connectivity page and in section 7 of `docs/common_mistakes.md`. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-04 Similarity and artifact figures

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/03_representational_similarity_jrsa.md`, `docs/05_artifact_detection_and_repair.md`.
Source: the "Top 10" list of the figure inventory of 2026-10-04, a read-only survey at `9cf0bb0f`,
numbered as there. Each figure is synthetic unless its bullet says otherwise, generated by
`docs/generate_figures.py` in the figure style ruled 2026-10-04 in light and dark, its caption naming each jnwb
function it calls.
- Inventory 5: RDMs and jRSA windows are text only. Check: two RDMs and a windowed jRSA trace against its null (`rdm`, `rdm_similarity`, `jrsa(null=)`) on the jRSA page, not through `JRSAResult.plot()`, whose figure size is fixed. Waits: documentation only; no number changes.
- Inventory 7: bad-channel and bad-trial detection have no figure. Check: the channel-correlation matrix, the flagged channels and the consensus bad-trial map on the artifact page. Waits: documentation only; no number changes.
Accept: the figure tests and `scripts/docs_form_gate.py` pass; each page shows its figures in light and dark.
Stop: a figure would need a function outside `jnwb.__all__`.

### 14-05 Tutorial figures through the docs generator

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-figures. Blocked by: none.
Writes: `docs/generate_figures.py`, `docs/assets/figures/**`, `docs/tutorials/*.md`, `examples/tutorials/09_open_data.py`, `tests/test_synthetic_figures_are_labelled.py`.
Ruled 2026-10-04: tutorial pages 00 to 09 get figures through the docs generator. Per the figure
inventory of 2026-10-04, tutorial 04 prints its PSD, TFR and wPLI, tutorial 06 its CSD, vFLIP, zFLIP
and xFLIP, and tutorial 09's clock table is text only.
- Tutorials 00 to 09 show no figure. Check: each page embeds a generated figure in light and dark, or this item records why the page needs none. Waits: documentation only; no number changes.
- Inventory 3, empirical: a PSTH by layer and 50-80 Hz dB by depth (`raster_psth`, `aggregate_to_db`) from the committed excerpt on the open-data tutorial. Check: the figure, and an EMPIRICAL entry for it in `tests/test_synthetic_figures_are_labelled.py`. Waits: documentation only; no number changes.
- `examples/tutorials/09_open_data.py` writes a light-only PNG to a temporary folder, outside the generator. Check: the figure comes from `docs/generate_figures.py` in light and dark. Waits: documentation only; no number changes.
Accept: the figure tests, `tests/test_open_data_example.py` and `scripts/docs_form_gate.py` pass.
Stop: a figure would need data the repository does not carry.

### 11-04 Proposals for the pitfall estimators

Release: deferred-0.2.10.
AUTONOMY: none for the shape; the proposal is `max`.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 10-11.
Writes: `artifacts/evidence/0.2.11/pitfall_estimators_proposal.md`.
Ruled 2026-09-29: all four in scope, each shape ruled before code.
- Nonparametric Granger by spectral factorization (Wilson), for comparison with the published values. Check: the proposal names the reference, the signature and a synthetic identity against the parametric path at the true order.
- A time-reversed Granger control for SNR asymmetry. Check: the proposal states the decision rule and its reference.
- Partial coherence conditioned on a third signal. Check: signature and reference.
- A bias floor for coherence and Granger from randomly paired epochs (Vezoli et al. 2021). Check: signature, the pairing scheme and its `rng`.
Accept: Hamm rules each shape; the implementation becomes its own item with API, docs and tests before any skill row.
Stop: public API; Hamm rules the shape.
Waits: public API; Hamm rules the shape.

### 14-06 The pitfall estimators Hamm rules

Release: deferred-0.2.10.
AUTONOMY: none until Hamm rules each shape from 11-04's proposal.
Role: jnwb-developer. Skill: jnwb-connectivity. Blocked by: 11-04.
Writes: `jnwb/connectivity/**`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `tests/test_connectivity.py`, `tests/test_connectivity_pitfalls.py`, `docs/08_directed_connectivity_and_information.md`, `docs/references.md`, `changelog.d/pitfall-estimators.added.md`.
11-04's acceptance makes the implementation its own item, with API, docs and tests before any skill row.
- The four estimators of `artifacts/evidence/0.2.11/pitfall_estimators_proposal.md` (nonparametric Granger by spectral factorization, a time-reversed Granger control, partial coherence, a bias floor from randomly paired epochs) have no implementation. Check: each ruled estimator ships with its signature, a `docs/references.md` row and a synthetic test, and the 10-11 test that names its gap asserts the repair. Waits: public API; nothing lands before the ruling.
Accept: the suite and harness pass; the packet reports the `docs/api.md` rows and the changelog text.
Stop: an estimator whose shape Hamm has not ruled.

### 13-04 A screen fitted to caller-supplied curation labels

Release: deferred-0.2.10.
AUTONOMY: none.
Role: jnwb-developer. Skill: jnwb-statistics. Blocked by: the collaborator's label-learning skill.
Writes: `jnwb/unit_quality.py`, `jnwb/__init__.py`, `jnwb/_lazy_exports.py`, `tests/test_unit_quality_screen.py`, `docs/09_decoding_and_visual_qc.md`, `docs/common_mistakes.md`, `examples/unit_quality.ipynb`, `changelog.d/unit-quality-screen.added.md`.
Ruled 2026-10-03: decided later. When the collaborator's label-learning skill arrives, this
design and theirs go to Hamm, who rules the screen into the core or deletes this item so the
downstream skill composes 13-03's measures. Features are 13-03's measures
plus caller columns; labels are the caller's human index; `groups` is the session; `rng` is
required.
- Held-out agreement per session (balanced accuracy and Cohen's kappa against the labels), never pooled across sessions alone. Check: a synthetic corpus whose sessions differ in label rate shows the pooled and per-session values differ.
- Declines when one label class is present, when fewer than two sessions exist, or when a feature is constant across units. Check: one test per refusal.
- The result names what it estimates: agreement with this curator's labels, not unit isolation. Check: the docstring and skill row say so; a test reads the result's `estimand` field.
- The worked example's screen: the 0.2.9 notebook keeps the measures, the plot and the routing, and the screen with its per-session agreement table moved here on 2026-10-04. Check: `examples/notebooks/unit_quality.ipynb` applies the screen, shows held-out agreement per session, and runs under `tests/test_notebooks.py`.
Accept: the suite and harness pass; the downstream evaluation on the curated datasets is recorded downstream, with only its summary numbers in `artifacts/evidence/0.2.9/`.
Stop: the collaborator's skill reaches a different design; both go to Hamm.

### 14-08 Unit-curation rows only the lab pipeline holds

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-qc. Blocked by: access to the lab pipeline's code.
Writes: `artifacts/evidence/0.2.9/unit_qc_inventory.md`.
Split from 10-15 on 2026-10-05 (ruled): these rows are defined only in the lab pipeline (`yihan777/alpha_beta_mechanism@826e540`), which no one here can read.
- D1, D9 and the lab meaning of D3 ("mirrored") are defined only in that pipeline. Check: each row cites its code once its owner gives access. Waits: study-specific rows; jnwb's measures are unchanged.
Accept: each check passes.
Stop: none.

### 14-07 A trial-based noise correlation, if a user needs it

Release: deferred-0.2.10.
Role: jnwb-developer. Skill: jnwb-spiking. Blocked by: none.
Writes: `jnwb/spiking.py`, `tests/test_spiking.py`, `skills/jnwb-spiking/SKILL.md`.
Source: 09-08's conditional bullet, moved whole on 2026-10-04; 09-08 keeps its window and bin-count
edges in 0.2.10.
- A trial-based noise correlation (Cohen and Kohn's $r_{sc}$, counts per trial in a window) beside the time-bin form, if jaxfne or a study needs it. Check: Hamm rules whether it is a mode or a function. Waits: the docstring, references row and skill now say the time-bin form includes signal correlation.
Accept: the ruled form closed with a test, or the item deleted when no user needs it.
Stop: public API; Hamm rules the shape.
