# 0.2.5

Audited read-only at `3f432306` (0.2.4, released and served by PyPI) across code, tests,
docs, skills, packaging, CI and backends. Each item carries the observation that produced it.
Items are deleted when done; finished work is not recorded here.

What the green state did not prove: the suite runs against the checkout and never against the
installed wheel (`pythonpath = ["."]`); `docs/api.md` is generated from `__all__` and then
checked against it; gate 5 is satisfied by its own generator; and a declared hard dependency
can be absent while 1465 tests pass, because two modules convert the `ImportError` into NaN.

## Execution protocol (authorized 2026-09-16)

The stack is frozen. It is executed to empty in dependency batches, not as 84 approval cycles:
A `05-01..25` scientific correctness, B `26..42` API and NWB, C `43..52` performance and
backend, D `53..60` tests, E `61..66` docs, F `67..72` skills and agents, G `73..78` packaging,
H `79..82` harness, I `83..84` independent critic and release.

Within a batch: reproduce, repair, add the discriminator, continue. Critical and high findings
are reproduced first. **A finding that does not reproduce is marked unsupported with its
evidence and its item deleted -- correct code is not modified to match a wrong audit.** One
batch-level regression and gate run, then commit and push, then the next batch.

The numbering controls coverage, not ordering: when a defect being repaired is mechanically
preventable, the smallest relevant repair from `05-79..82` is applied in that batch rather than
deferred to H, so later work benefits from the gate.

Qualification runs in a clean environment built from the declared extras, or in CI. The
development `.venv` described at the end of this file is not package evidence.

## 1. Scientific correctness

### 05-85 The cone of influence marks half the region edge effects actually reach
- **Problem** Found while repairing 05-03. `coi_mask` is built from `coi_sigma` (default 2.0) while the kernel is truncated at `cutoff_sigma` (default 4.0), so samples between 2 and 4 sigma of the edge convolve against `mode="same"` zero-padding and are marked valid.
- **Evidence** Unit cosine on a 1000-unit DC offset, DC-corrected kernel, 4000 samples at 1 kHz. Contamination ends exactly at the kernel half-width `ceil(cutoff_sigma * sigma_t * fs)` -- first clean index 191 / 319 / 637 at `n_cycles` 3 / 5 / 10 -- while `coi_mask` clears at 96 / 160 / 319. Max difference *inside* the mask: 27.1 / 18.6 / 9.42 on a unit-amplitude signal.
- **Change** Derive the COI from the kernel support rather than an independent multiplier, or require `coi_sigma >= cutoff_sigma` and say so. `ComplexTFR`'s docstring is honest about what `coi_mask` currently means, so this is a default that does not serve the use `docs/04` puts it to; sequence it with 05-65.
- **Preserves** An explicitly passed `coi_sigma`.
- **Discriminator** No sample marked valid by `coi_mask` responds to a constant offset.
- **Accept** `test_probe09_edge_and_coi_exact_boundary` and `test_probe14` are retargeted to the new contract, and `docs/04` states what the mask excludes and why an average must be taken after masking.

### 05-13 `band_power` returns mean PSD while documenting "power in band"
- **Problem** `float(np.mean(pxx[mask]))` is bandwidth-independent, so bands of different widths are not comparable as power.
- **Evidence** `band_power(x, fs=1000., freq_range=(19.,21.), normalize=False)` = 0.22175471142697917, exactly `mean(PSD[mask])`; `np.trapezoid(PSD[mask], f[mask])` = 0.48715.
- **Change** State the estimand and its units in the docstring; consider an `integrate=` option. Documentation change, not a numerical one.
- **Preserves** All current values.
- **Discriminator** The docstring names mean spectral density and its units.
- **Accept** `docs/04` and the docstring agree on the estimand.

## 2. Silent and fabricated failure

### 05-21 Silent truncation and mis-pairing across four entry points
- **Problem** Each shortens or drops input where a sibling refuses.
- **Evidence** `as_trials([500,480,500], allow_ragged=True)` -> `(3,480)` with `warnings == []` (log only), while `allow_ragged=False` raises `ragged trial lengths [480, 500]`. `paired_fire_prob_test` with lengths 8 and 4 returns `risk_difference=0.5` pairing unrelated trials, while `shuffle_pvalue_paired` raises for exactly this and its docstring names the harm. `jrsa` with `nan_policy='propagate'` accepts `(60,6)` against `(40,6)` and silently uses the first 40, while the default policy raises. `bin_spikes` drops NaN spike times with no count.
- **Change** `warnings.warn(..., RuntimeWarning)` alongside the ragged log; length-equality check in `paired_fire_prob_test`; hoist the `jrsa` shape check above the `nan_policy` dispatch; count and report non-finite spike times.
- **Preserves** Every equal-length, finite path.
- **Discriminator** Each case warns or raises; none returns a quietly shortened result.
- **Accept** One parametrized mismatch test covering all four.

### 05-23 Metadata readers turn a bad path into an empty cohort
- **Problem** `on_read_error="skip"` plus a broad exception tuple makes a nonexistent file, an unreadable file and a genuinely empty table indistinguishable, reported through `log.error`, which `warnings`, `pytest.warns` and `-W error` cannot see.
- **Evidence** `get_all_units_metadata(bad_path)` and `electrode_inventory(bad_path)` -> `DataFrame (0,0)` with zero warnings, while `inspect`, `events` and `unit_spike_times` all raise `FileNotFoundError` on the same path. Separately, `electrode_inventory` requires an int-parsable filename stem: a valid 4-electrode file named `mm_depth.nwb` -> `DataFrame (0,0)` with `invalid literal for int()`, while `get_all_units_metadata` on that file returns `(2,10)`.
- **Change** Raise when every input path failed; reuse the int-or-string session fallback from `metadata.py:57` at `:341`.
- **Preserves** Per-file skipping within a genuine multi-file call.
- **Discriminator** A single bad path raises; a non-numeric filename returns the electrodes.
- **Accept** All four NWB readers agree on a nonexistent path.

### 05-24 `cluster_permutation_test` turns an Inf sample into a measured zero
- **Problem** The entry guard checks `np.isnan` only, and `np.divide(..., out=np.zeros_like(m), where=se > 0)` leaves the pre-filled 0.0 when `se` is NaN.
- **Evidence** X `(20,30)` with `X[0,0]=inf`, paired: `stat_map[0] == 0.0`; without the Inf the same point gives 2.26238157.
- **Change** Guard with `np.isfinite(X).all()`; fill with NaN rather than 0.0; `statistics.py:1490`, `:1545`.
- **Preserves** Finite input.
- **Discriminator** An Inf sample raises rather than guaranteeing that point joins no cluster.
- **Accept** Inf and NaN are rejected identically.

### 05-25 An empty selection returns fabricated zeros in one module and NaN in another, and both are test-enforced
- **Problem** `trajectory.py` and `analyzers.py` take opposite positions on the same condition, each pinned by a passing test (`test_trajectory.py:112` enforces zeros; `test_analyzers_coverage.py:106` enforces "NaN, not fabricated zeros").
- **Evidence** Both green at `3f432306`.
- **Change** Ruled 2026-09-16: an explicitly requested population with no observations yields an *unavailable* estimate, never zero. Reconcile `trajectory.py` toward the non-fabrication semantics already in `analyzers.py`. Use NaN where the return type is a float array; use `None` or an explicit availability field where the structured type supports it. Zero stays valid only when zero was estimated from observations. Retarget `test_trajectory.py:112`.
- **Preserves** Every non-empty selection, and `analyzers.py`'s current behaviour.
- **Discriminator** One documented empty-selection policy across the package; reintroducing the fabricated zero fails a test.
- **Accept** The policy is stated in `docs/common_mistakes.md`, both tests assert it, and no public function returns 0.0 for a selection it did not observe. This is `AGENTS.md` invariant 1.

## 3. API consistency

### 05-26 `jrsa` records the device and options it was asked for, not the ones that ran
- **Problem** `jrsa` is the only compute module that bypasses `_backend.py`, and its provenance echoes the request.
- **Evidence** With `cupy_available()` False: `jrsa(device='cuda', backend='cupy')` warns "CuPy not available; falling back to NumPy" and then records `execution == {'backend':'cupy', 'device':'cuda', ...}`. `device='bogus_device'` runs and is recorded verbatim, while all 15 `resolve_device` sites raise `ValueError` for the same string. `correction='bonferoni'` warns it fell back to `fdr_bh` and records `parameters['correction'] == 'bonferoni'`. `metric='cka', kernel=` is accepted and ignored: `linear`, `rbf` and `nonsense_kernel` all return 0.14404010802537645. On a live A4000 the cupy path is bit-identical to CPU (`max|diff| = 0.0`) because `_ensure_np` converts at the head of all 14 metrics, so the upload is discarded while the claim stands.
- **Change** Route `device` through `resolve_device`; record the resolved backend and device; raise on an unknown `correction`; raise `NotImplementedError` for `kernel != 'linear'`; delete `_autodetect_backend` and the `_backend_*` helpers; `jrsa.py:964`, `:919`, `:1270`.
- **Preserves** Numerical results on the NumPy path.
- **Discriminator** No call leaves `execution` disagreeing with the warning emitted during it.
- **Accept** `jrsa` rejects an unknown device name like every other routed function, and its provenance matches what executed. This is `AGENTS.md` invariant 6.

### 05-27 `resolve_interval_table` does not take a path
- **Problem** The only exported NWB entry point requiring an open `NWBFile`, with `table` required positionally and no keyword-only discipline.
- **Evidence** Live signature `(nwb: NWBFile, table: str | None) -> str` against its exact sibling `resolve_acquisition(path_or_nwb, name=None)`. A path gives `AttributeError: 'str' object has no attribute 'intervals'`.
- **Change** Wrap in `_with_nwb` as `resolve_acquisition` already is; default `table=None`; `nwb_events.py:78`.
- **Preserves** The `trials` -> sole-table -> ambiguity precedence and every accepted name form.
- **Discriminator** A path resolves; a wrong type raises a jnwb error naming both accepted types.
- **Accept** One path-or-`NWBFile` convention across every exported NWB function, stated in the docs (neither `NWBInput` nor `InspectInput` is expanded anywhere today).

### 05-28 No exception base is reachable, and contract violations arrive as incidental errors
- **Problem** `nwb_events.NWBEventError` exists with four exported subclasses but is not in `__all__`; `nwb_io.MissingRequiredNWBFieldError` is documented at `docs/01:50` and is neither based nor exported; 350 of 397 raises are bare `ValueError`; `ChannelIndexError` inherits `IndexError` while its three siblings inherit `Exception`.
- **Evidence** `hasattr(jnwb, 'NWBEventError')` and `hasattr(jnwb, 'MissingRequiredNWBFieldError')` are both False. `probe_geometry("x.nwb")` raises a bare `AssertionError` with an empty message (`addressing.py:587`), which disappears under `python -O` and then executes `coords.shape` on `None`.
- **Change** Export both names; give `ChannelIndexError` its siblings' base; replace the bare assert with a `TypeError` naming the accepted types.
- **Preserves** Existing exception identities, so current `except` clauses keep working.
- **Discriminator** `except jnwb.NWBEventError` catches all four subclasses.
- **Accept** Every exception class named in the docs is importable from `jnwb`.

### 05-29 Unit-suffix divergence puts a 1000x error one keystroke away
- **Problem** `_ms` (23 parameters) and `_s` (7) coexist on functions used in the same workflow, and the response/baseline windows carry no unit at all.
- **Evidence** `examples/tutorials/03_spiking.py` calls `raster_psth(..., win_ms=(-100.,400.))` at line 38 and `compute_response_metrics(..., baseline_window=(-0.2,0.0))` at line 61 in the same body; both take a float 2-tuple and the second names no unit. `api.md:235` shows `baseline_window: Tuple[float,float] = (-0.25,-0.05)`, still with no unit. `epoch_continuous(win_s=)` is the other `_s` outlier against `raster_psth(win_ms=)`.
- **Change** Add `_s` suffixes to the four unsuffixed window parameters, aliasing the old spelling with conflict detection, using the pattern `band_power(fs=, sampling_rate=)` already implements at `spectral.py:173`.
- **Preserves** Existing call sites through the alias.
- **Discriminator** Passing both spellings raises `Conflicting values`.
- **Accept** Every time or window parameter in `__all__` carries its unit in its name.

### 05-30 `alternative=` is unvalidated and the paired/unpaired siblings default differently
- **Problem** An `if/elif/else` whose fallthrough is two-sided.
- **Evidence** `shuffle_pvalue_paired(..., alternative="GREATER")` and `alternative="nonsense"` both return p = 0.03, the two-sided value. `shuffle_pvalue_paired` defaults `"two-sided"`; `shuffle_pvalue_unpaired` defaults `"greater"`; on one dataset that is p = 0.03 versus 0.227. `exact_sign_flip` validates and case-folds the identical parameter at `statistics.py:152`.
- **Change** Validate against `{"two-sided","greater","less"}` with `.lower().strip()`; make both defaults two-sided.
- **Preserves** Explicitly passed valid values.
- **Discriminator** A typo raises instead of silently selecting two-sided.
- **Accept** Both siblings share a default and reject unknown values. Same treatment for `confirmatory_compare`, which accepts `alpha=2.0` and returns `confirmed_parametric=True` while `clopper_pearson` validates `0 < alpha < 1`.

### 05-31 `fs` and 2-D input are validated inconsistently across the spectral surface
- **Problem** `_resolve_fs` never checks positivity, and `imaginary_coherency` ravels 2-D input that `cross_area_coherence` rejects.
- **Evidence** `wpli(x, y, fs=0.0)` -> `ZeroDivisionError`; `fs=-1000.` -> a `ValueError` describing a grid "0 to -500 Hz in steps of -3.90625 Hz"; `imaginary_coherency` with the same `fs` gives a clean `ValueError`. `imaginary_coherency(np.stack([x,y]), np.stack([y,x]), fs=1000.)` returns `{'icoh_mean': 0.0061, ...}` by concatenating channels end to end; `cross_area_coherence` refuses 2-D with a detailed message.
- **Change** Add `fs > 0 and np.isfinite(fs)` to `_resolve_fs` (`spectral.py:173`); reject `ndim != 1` in `imaginary_coherency` (`:1401`).
- **Preserves** 1-D behaviour.
- **Discriminator** Every spectral entry point gives the same error class for `fs=0` and for 2-D input.
- **Accept** One parametrized bad-`fs` and bad-shape test across the spectral surface.

### 05-32 `jnwb.ontology` is 11 public symbols no workflow can reach
- **Problem** 387 lines, 11 exported dataclasses and 3 factories, with zero call sites in `jnwb/`, zero behavioural tests, and zero mentions in `skills/`, `examples/` or `README.md`. The module states the constructors "are intentionally absent... a generic implementation would have nothing to read from".
- **Evidence** `Dataset, AlignedDataset, Alignment, EpochCollection, Question, Interpretation, Provenance, Lineage` are never mentioned anywhere under `tests/`; `Query`'s only behavioural line asserts a value the test just set. `create_aligned_dataset`, `create_result` and `create_figure` each return exactly one grep hit across the whole repository: their own definition.
- **Change** Ruled 2026-09-16: retain the public surface. "No caller in this repository" is not evidence of no downstream caller, and a public library exists for callers a repository search cannot observe. Evaluate each of the 14 exports against `distinct useful operation AND documented AND tested AND generic`; remove or deprecate only those that fail, with a `CHANGELOG.md` entry and a deprecation path per `AGENTS.md` section 8. Do not reduce the API to improve an internal usage metric. The audit's evidence is therefore a documentation-and-test gap, not a removal case.
- **Preserves** Import compatibility and every retained symbol.
- **Discriminator** Every retained name has a behavioural test that fails when its operation breaks.
- **Accept** No symbol in `__all__` lacks a test and a documented use; every removal cites the four-part criterion, not a call-site count.

## 4. Reproducibility and statistics

### 05-33 `jrsa` records the generator state under the name `seed`
- **Problem** `_make_exec_meta` reads `rng.bit_generator.state["state"]["state"]`.
- **Evidence** `jrsa(..., random_state=7).execution["seed"]` -> 69277902251545625047243999639177715869, which cannot be fed back to reproduce the run.
- **Change** Record the `random_state` argument; `jrsa.py:1663`.
- **Preserves** Determinism, which is already correct: all 14 metrics reproduce bit-identically at a fixed `random_state`.
- **Discriminator** `execution["seed"]` round-trips as a `random_state`.
- **Accept** Feeding `execution["seed"]` back reproduces the result.

### 05-34 `nested_cv_linear_svm` gives the caller no control over the partition
- **Problem** The signature is `(X, labels, n_splits)` with `random_state=42` hardcoded at four sites, so partition sensitivity cannot be assessed.
- **Evidence** `decoding.py:86, 91, 113, 124`. Separately, `shuffle_r2_ci` spells it `random_state: int` and `cross_modal_comparison` spells it `seed`, against the package's dominant `rng: np.random.Generator`.
- **Change** Add a `seed`/`rng` parameter to `nested_cv_linear_svm`; alias the divergent spellings as `jrsa` now does, with conflict detection.
- **Preserves** Current results at the existing default.
- **Discriminator** Two different seeds give two different fold assignments.
- **Accept** Every randomized public function takes a caller-supplied generator under one spelling. The RNG vocabulary is currently 10 spellings across 19 functions: `rng` 8, `seed` 7, `random_state` 3, `n_surrogates` 7, `n_permutations` 3, `n_shuffles` 3, plus the singletons `permutations`, `n_shuffle`, `n_bootstrap`, `random_seed`.

### 05-35 Hidden default seeds make two "independent" runs share a null
- **Problem** `exact_sign_flip`, `_bootstrap_mean_diff_ci`, `bootstrap_ci` and `permutation_test` fall back to `np.random.default_rng(42)`; `cluster_permutation_test` uses `default_rng(0)`.
- **Evidence** `statistics.py:206, 680, 953, 993` and `:1483`; probed reproducible across calls.
- **Change** Name the constant in the signature so it is visible, or require an explicit `rng`.
- **Preserves** Reproducibility.
- **Discriminator** The default seed is discoverable from the signature.
- **Accept** No randomized function hides its default seed in the body.

### 05-36 `decoding` label handling refuses valid data and accepts invalid data
- **Problem** `np.bincount(labels.astype(int)).min()` counts absent label values as classes of size 0, and `build_inner_validation_partitions` casts group ids with `int()`.
- **Evidence** Same X `(40,5)`, 20 per class, separable: labels `{0,1}` -> `accuracy=0.825, status="success"`; labels `{1,2}` and `{0,2}` -> `status="insufficient_trials_for_cv"` with all metrics NaN (`np.bincount([1,1,2,2]).min() == 0`); labels `{-1,1}` -> `ValueError: 'list' argument must have no negative elements`; labels `{'a','b'}` -> `ValueError: invalid literal for int()`. `assign_outer_folds` accepts string `cycle` ids and returns `outer_fold_status="valid"`, then `build_inner_validation_partitions` on that output raises `invalid literal for int() with base 10: 'c1'`.
- **Change** `np.unique(labels, return_counts=True)[1].min()`; drop the `int()` casts at `decoding.py:262`, `:264`; check `len(np.unique(labels)) >= 2` before `max_splits`.
- **Preserves** Contiguous 0-based integer labels.
- **Discriminator** Any two-class label set of adequate size decodes; the documented two-step pipeline round-trips its own group ids.
- **Accept** `status` never asserts something false about the data.

## 5. NWB and user workflow

### 05-37 jnwb cannot read a minimal NWB units table that pynwb reads
- **Problem** The length-1-array-to-scalar repair collapses `colnames=array(['spike_times'])` to the string `'spike_times'`, and the next line does `list(...)` on it.
- **Evidence** A units table whose only column is `spike_times`, written with plain pynwb. pynwb reads it: `units n = 2, colnames = ('spike_times',)`. jnwb: `ConstructError ... 'colnames': array(['s','p','i','k','e','_','t','i','m','e','s','spike_times'])`. Every entry point fails — `inspect`, `events`, `unit_spike_times`, `acquisition_channel`, `get_all_units_metadata`, `electrode_inventory` — and tutorial 00 dies with `KeyError: 's'`.
- **Change** Exclude `colnames` from the scalarization at `nwb_io.py:43`, or guard `:58` with `np.atleast_1d` / an `isinstance(value, str)` check.
- **Preserves** The scalar repair for the attributes it was written for.
- **Discriminator** A single-column units table is readable through every entry point.
- **Accept** A fixture written with plain pynwb, carrying one units column, passes the whole documented workflow. This is the most common minimal table a foreign lab writes.

### 05-38 `acquisition_channel` ignores the layout `inspect` computed
- **Problem** It slices axis 1 unconditionally and bounds-checks `shape[1]`, never consulting the `layout` its own sibling reports.
- **Evidence** Channel-major `(64, 1000)` data with 64 electrodes: `inspect` reports `layout: channel_by_time`; `acquisition_channel(channel=999)` returns a 64-sample time slice presented as a channel trace at 1000 Hz; `channel=1000` raises `Channel index 1000 out of range for series 'es' with 1000 channels`. Separately, the layout heuristic itself is `shape[0] >= shape[1]` with no reference to the electrode count, so a 50-sample x 100-channel recording is reported `channel_by_time` while the same dict carries `electrodes n_rows = 100`.
- **Change** Decide the axis by matching a dimension against `len(nwb.electrodes)`; emit `layout: 'ambiguous'` when both or neither match; have `acquisition_channel` honour it; `nwb_inspect.py:151, 187, 359, 496`.
- **Preserves** Time-major files, and the verified-correct `conversion`/`offset` scaling.
- **Discriminator** A channel-major file either returns the correct trace or raises naming the layout; the bound check reports the true channel count.
- **Accept** Both orientations round-trip, with the electrode count as the arbiter.

### 05-39 `inspect(path)` and `inspect(NWBFile)` return different schemas
- **Problem** Two independent implementations, an h5py walk and a pynwb walk, with no shared schema; and `_find_series_leaf` takes the first `data` leaf and the first `rate` leaf independently.
- **Evidence** `inspect(path)` acquisition keys include `data_path` and `layout`; `inspect(NWBFile)` omits both. Interval columns: path gives `['id','start_time','stop_time']` with `shape` and dtypes `int64,float64,float64`; NWBFile gives `['start_time','stop_time']` with no `shape` and dtypes `float64,float64`. `units`: path gives `{'n_rows','columns','has_spike_times'}`, NWBFile gives `{'n_rows'}`. On one legal file with an `LFP` container holding `lfp_alpha` (1000 Hz) and `lfp_beta` (500 Hz): `inspect(path)` reports `rate_hz: 500.0` with `data_path` pointing at `lfp_alpha`, `inspect(NWBFile)` reports `rate_hz: 1000.0`, and `acquisition_channel` returns `lfp_alpha` at 1000 Hz — three answers for one object.
- **Change** One builder producing one schema; iterate `electrical_series` explicitly and raise `AmbiguousAcquisitionError` when a container holds more than one. Also raise on an acquisition/processing name collision, which is currently resolved by precedence with no warning (`nwb_inspect.py:359`).
- **Preserves** The path-based schema, which is the richer one.
- **Discriminator** The two call forms return equal dicts for the same file; a multi-series container refuses rather than picking.
- **Accept** Passing an open handle, the only documented way to avoid reopening the file, does not change the answer.

### 05-40 Onsets in milliseconds are accepted as seconds and produce a confident number
- **Problem** `time_unit="seconds"` is asserted as a literal and never checked against the file's own extent.
- **Evidence** A file with onsets 1000-5000 and a 1.0 s recording: `events()` returns `EventTable(time_unit='seconds', onsets=[1000. 2000. ...])` with no warning; `epoch_continuous` returns `(5, 800)` with all five rows NaN and no warning; tutorial 00 prints "5 events, onsets in seconds ... spectral peak at 0.0 Hz". Relatedly, `epoch_continuous` on a NaN onset returns shape `(1,0)` with a numpy overflow warning, where `events()` raises `InvalidOnsetValueError` for the same NaN.
- **Change** Warn in `epoch_continuous` when most epochs fall entirely outside the data under `boundary_policy="nan"`; reject non-finite onsets there with the same `InvalidOnsetValueError` `events` uses.
- **Preserves** Legitimate partially-out-of-bounds epochs.
- **Discriminator** A wholly out-of-range onset set warns or raises rather than returning all-NaN epochs.
- **Accept** The three entry points agree on a NaN onset.

### 05-41 The errors a first-time user meets are documented nowhere but the generated reference
- **Problem** Ten of 151 public symbols appear in no hand-written page, and eight of them are the NWB resolvers and error types.
- **Evidence** Symbols present in `docs/api.md` and in no other `docs/**/*.md`: `resolve_acquisition, AmbiguousAcquisitionError, AcquisitionNotFoundError, ChannelIndexError, UnitNotFoundError, EventTable, resolve_interval_table, IntervalTableNotFoundError, InvalidOnsetValueError, DETECTION_TAILS`. No troubleshooting page, error index or traceback-to-fix table exists in the nav. The nearest guidance is on `docs/agents.md`, a page this reader was routed past.
- **Change** One short page: each error class, what produced it, and the argument that resolves it. `AmbiguousIntervalTableError` is the model — it is explained in three places before it can fire, and that is the best writing on the site.
- **Preserves** The existing refusals, which are correct.
- **Discriminator** Every exported error class is explained on a hand-written page.
- **Accept** Gate 5 is replaced by a check that every `__all__` symbol appears outside the generated reference (see 05-66).

### 05-42 Tutorial 00 crashes on the two most common foreign-file shapes
- **Problem** It reads `acquisition['rate_hz']` unguarded and iterates only `info["acquisitions"]`.
- **Evidence** A file with `timestamps` instead of `starting_time`+`rate` -> bare `KeyError: 'rate_hz'`. A file whose LFP lives in a processing module -> no acquisition line printed at all; `'processing_continuous'` never appears in the script.
- **Change** Guard the key and fall back to `info["processing_continuous"]`; `examples/tutorials/00_your_own_file.py:110`.
- **Preserves** The discovery-not-assumption design, which is verified working: on a 16-channel foreign file it found `condition` as the code column and recovered the injected 23.0 Hz.
- **Discriminator** Irregularly-sampled and processing-module files complete the tutorial.
- **Accept** Tutorial 00 runs against all fixture shapes in `jnwb/testing/nwb_fixtures.py` plus a timestamps-only file.

## 6. Performance and backend

### 05-43 Device changes the number
- **Problem** `gpu_pca` computes in float64 on CPU and float32 on CUDA, and neither it nor `compute_population_trajectory` pins an SVD sign convention.
- **Evidence** On a live RTX A4000, `gpu_pca(X(4000,60), n_components=3)`: `cpu dtype float64` against `cuda dtype float32`, component signs `[+1, -1, -1]`, raw `max|cpu-cuda| = 8.005`; after sign alignment 6.48e-04. `compute_population_trajectory` shows `max_rel = 2.0`, the signature of a sign flip, with sign-aligned agreement at 2.71e-12.
- **Change** Match the CPU dtype on the CUDA branch; pin a deterministic sign (force the max-abs loading of each component positive) once, before the device branch; `gpu_pca.py:69`, `trajectory.py:151`.
- **Preserves** Numerical content up to the pinned sign.
- **Discriminator** CPU and CUDA outputs are equal to float64 tolerance without post-hoc sign alignment.
- **Accept** This is `AGENTS.md` invariant 6: "Device and worker count never change a number." The prior receipt's claim that parity is bounded by 3.6e-04 covers only sign-aligned components and should be corrected; the call-site count is 15, not 13.

### 05-44 Two `device=` sites deny the GPU silently
- **Problem** One discards the resolver's result; the other gates the GPU branch off after resolution.
- **Evidence** `vflip(..., device='cuda')` on a live A4000: `h2d=0, d2h=0`, zero warnings — `laminar.py:220` assigns to `_`. `fit_var_bivariate(..., device='cuda', ridge=0.1)`: `h2d=0, d2h=0`, no warning, because `and ridge <= 0` gates the branch; with `ridge=0` the GPU is reached at 3.81x. Without a GPU the caller is warned; with one they are silently denied, inverting the contract.
- **Change** Drop `device` from `vflip`'s signature or warn as `rdm` does; emit `warn_device_fallback` when `ridge > 0` forces the CPU branch; `connectivity.py:206`.
- **Preserves** Numerical results.
- **Discriminator** Every `device='cuda'` call either reaches the GPU or warns.
- **Accept** All 15 resolver sites have a consistent denial contract. Also fix the two sites whose warning names a private callee (`fit_var_bivariate`) rather than the public function.

### 05-45 Three CUDA paths are slower than CPU, one by 28x
- **Problem** Python loops with per-iteration host/device transfers.
- **Evidence** `UnitAnalyzer.acg` at >= 30k spikes: CUDA 32231 ms against CPU 1151 ms (0.036x), with 80002 host-to-device and 240002 device-to-host transfers per call, from `int(lo[idx])`/`int(hi[idx])` inside the loop and a re-uploaded `bin_edges`. `_welch_csd_gpu` runs a 96-iteration Python segment loop: 21.94 ms against 1.83 ms for the same estimator strided, which is why `harmonic_analysis` (0.557x), `spectral_tilt` (0.567x) and `band_power` (0.44x) are all slower on CUDA. The CPU `_acg_vectorized` is separately 41-151x slower than an identical-output vectorisation (5k spikes 123.3 ms -> 0.8 ms, `array_equal == True`).
- **Change** Hoist `bin_edges` and use the gather the `<30000` branch already implements; build the segment matrix with one strided index; vectorise the CPU ACG; `analyzers.py:437`, `:459`, `spectral.py:1680`.
- **Preserves** Outputs bit-identically (verified for the ACG).
- **Discriminator** No `device='cuda'` path is slower than its CPU sibling.
- **Accept** Measured before and after on the same machine, recorded in `artifacts/benchmarks/`.

### 05-46 `jrsa` defaults to `n_jobs=-1` and is 125x slower for it
- **Problem** It is the only entry point overriding the shared module's documented default of 1.
- **Evidence** 40x6 inputs, `metric='cka'`, `permutations=500`: `n_jobs=1` 0.07 s, `n_jobs=-1` (the default) 8.75 s. `_parallel.py:65` states the rule: "Parallelism only pays when the total serial work exceeds roughly a second."
- **Change** Default `n_jobs=1`, or size-gate the pool inside `_parallel_map`; `jrsa.py:145`.
- **Preserves** Results, which are already invariant to `n_jobs`.
- **Discriminator** A small default-argument call does not start a process pool.
- **Accept** The default is no slower than serial at any input size.

### 05-47 `_optimal_contiguous_partition` re-sums a diagonal inside the DP inner loop
- **Problem** `interval_w` re-sums `np.diag(corr)[u:v]` per call, making an O(K n^2) DP into O(K n^3), while the off-diagonal term two lines above is already prefix-summed.
- **Evidence** 19.86 / 60.76 / 275.84 ms at n = 64/128/256 (about n^2.9); with a prefix-summed diagonal, 4.84 / 14.80 / 77.28 ms, and `block_bounds`, `boundaries` and `modularity` bit-identical at every n. Paid `n_surrogates + 1` times: at n=128 with the default 200 surrogates, about 12.2 s becomes about 3.0 s.
- **Change** `dcum = np.concatenate([[0.0], np.cumsum(np.diag(corr))])`; `diag_sub = dcum[v] - dcum[u]`; `laminar.py:1037`.
- **Preserves** Bit-identical output.
- **Discriminator** Same results, measured speedup.
- **Accept** 3.5x or better at n >= 128, outputs unchanged.

### 05-48 `import jnwb` costs about 2 s, and 80% of it is two eager submodules
- **Problem** `__init__.py` imports `rsa` and `nwb_inspect` at module scope, pulling `scipy.spatial.distance` + `scipy.stats` and `pynwb` -> `hdmf` -> `pandas`.
- **Evidence** `-X importtime`: total 1.875 s, `jnwb.rsa` 0.96 s cumulative, `jnwb.nwb_inspect` 0.54 s. Eager in `sys.modules` after import: scipy, pynwb, hdmf, h5py, pandas. Deferred and confirmed working: sklearn, statsmodels, matplotlib, joblib. jnwb's own frames cost about 1.3 ms.
- **Change** Move `rsa` into `EXPORT_MODULES`; the mechanism exists and works. `nwb_inspect` is harder because `jnwb.inspect` is the documented entry point, so treat it as a separate decision.
- **Preserves** `jnwb.rdm` and `jnwb.rdm_similarity` resolving on attribute access.
- **Discriminator** `scipy.spatial` is absent from `sys.modules` after `import jnwb`.
- **Accept** Import time roughly halves; `tests/test_import_lazy.py` covers the new deferrals.

### 05-49 The import benchmark measures itself and its receipt is five releases stale
- **Problem** `tracemalloc.start()` runs before `t0 = time.perf_counter()` inside the probe.
- **Evidence** The script reports 8076 ms warm; direct measurement without tracemalloc is 2124 ms median, and with tracemalloc 7209 ms — the script over-reports by 3.3x. `artifacts/benchmarks/import_profile.txt` states "jnwb 0.1.6 (111 public symbols)" against the current 0.2.4 and 151 symbols; nothing gates it, unlike the vflip receipt.
- **Change** Time the import in a probe without tracemalloc and measure peak memory in a separate process; `scripts/benchmark_import.py:34`. Add a receipt-staleness test mirroring `tests/test_vflip_calibration_receipt.py`, failing when the version in `import_profile.txt` differs from `jnwb.__version__`.
- **Preserves** The script's interface.
- **Discriminator** The reported number matches an independent wall-clock measurement.
- **Accept** The receipt regenerates and is gated. Also delete the superseded `vflip_calibration_0.2.2.md` and `vflip_calibration_raw.json`.

## 7. Code simplification

### 05-50 Nine symbols have no caller anywhere
- **Problem** Dead code carried in the package.
- **Evidence** Each returns exactly one grep hit across `jnwb/ tests/ examples/ docs/ skills/ scripts/` — its own definition: `_confidence_interval` (`jrsa.py:944`), `_chunk_tensor` (`jrsa.py:1022`), `_backend_numpy` (`jrsa.py:1034`), `compare_old_new_criteria` (`metadata.py:524`), `old_new_summary_table` (`metadata.py:567`), `create_aligned_dataset` / `create_result` / `create_figure` (`ontology.py:349, 354, 365`), `coef_rows` (`statistics.py:579`). No version shims exist below the declared floor: a scan for `sys.version_info`, `np.__version__`, `NumpyVersion` and friends across `jnwb/` returns zero hits.
- **Change** Delete, except the three `ontology` factories, which are settled by 05-32.
- **Preserves** Everything else; none is exported.
- **Discriminator** The suite and all 13 gates stay green.
- **Accept** Zero unreferenced module-level symbols in `jnwb/`.

### 05-51 Utilities implemented twice
- **Problem** Duplicate definitions that can drift.
- **Evidence** `_with_nwb` is byte-identical in `nwb_events.py:107` and `nwb_inspect.py:222`, differing only in the type-alias name — the only name defined twice in the package. `channel_correlation_matrix` (`artifact_detection.py:32`) and `trial_correlation_matrix` (`:83`) are AST-identical, both `np.corrcoef(np.asarray(x, dtype=float))`, differing only in docstring. `statistics.py` forwards `clopper_pearson`, `mann_whitney_p_floor` and `exact_sign_flip` from class to module and `fdr_correct` from module to class, so the delegation direction cannot be inferred; `clopper_pearson_ci` is an alias of a delegate. `_parallel_map` (`jrsa.py:1013`) exists only to change one default. `tfr_dir`/`meta_dir`/`conndb_dir` are three copies of one six-line body.
- **Change** One shared `_with_nwb`; keep both correlation names but have one call the other; state the delegation direction in each forwarder's summary line; parameterise the three path helpers.
- **Preserves** Every public name.
- **Discriminator** No helper body appears twice.
- **Accept** `_with_nwb` has one definition.

### 05-52 Five modules carry unrelated responsibilities
- **Problem** Module boundaries that no longer match the code.
- **Evidence** `laminar.py` (1831) holds three independent estimators with private helpers used by nothing else, splitting cleanly at lines 862 and 1476. `connectivity.py` (2144) interleaves spike-train information theory (`56-164` and `1728-2010`) with VAR/Granger (`167-1720`). `spectral.py` (1913) carries 208 lines of spatial re-referencing and CSD that belong with `laminar`. `jrsa.py` (1740) holds a private device subsystem duplicating `_backend.py` — deleted by 05-26. `statistics.py` (1633) duplicates its own module surface inside `StatisticalAnalysis` (565 lines, 5 pure forwarders). `analyzers.py` (779) holds three unrelated static-method namespaces with no shared state.
- **Change** Split along the named line boundaries, re-exporting from the original module names so no import breaks.
- **Preserves** Every import path and `__all__`.
- **Discriminator** `from jnwb.laminar import vflip` and `import jnwb; jnwb.vflip` both keep working.
- **Accept** No module carries two unrelated responsibilities; suite and gates green. Sequence this after sections 1-6, since it moves the code those items repair.

## 8. Test simplification

### 05-53 Assertions that cannot fail
- **Problem** Tests that are green regardless of the code.
- **Evidence** `test_docs_nwb_workflow.py:124` asserts a long string is absent from `re.findall` output, which returns match substrings that can never contain it — and `skills/jnwb-nwb-data/SKILL.md:57` does contain the forbidden token. `test_representative_workflow.py:171` installs an import blocker defining `find_module`, removed from the meta-path protocol in 3.12, so it blocks nothing on the 3.14.3 interpreter; its own docstring calls it "the load-bearing assertion", and `test_jnwb_frozen_boundary.py:123` does it correctly with `find_spec`. `test_jnwb_frozen_boundary.py:78` iterates `AUTHORIZED_EXCEPTIONS`, which is `set()`. `test_jnwb_core.py` puts its assertions inside `if 'error' not in result:`, so replacing every `StatisticalAnalysis` method with an error dict leaves 25 of 26 passing.
- **Change** Repair each to assert what its name says.
- **Preserves** Intended coverage.
- **Discriminator** Each fails when the condition it names is reintroduced.
- **Accept** Verified by mutation, one mutation per repaired test.

### 05-54 Estimators with no discriminating test
- **Problem** Mutating the implementation changes no test result.
- **Evidence** Forcing `imaginary_coherency`'s `icoh_mean`/`icoh_abs_mean` to 0.0 changes zero of 1483 tests — every assertion is a null case or a self-comparison, in a file named `nonfabrication`. Mutating `shuffle_pvalue_paired`/`unpaired` to `1/(n+1)`, `shuffle_r2_ci.p_val` to 0.001, `paired_fire_prob_test.p` to 0.0001, `confirmed_*` to `True`, and `fdr_correct` to `return p.copy()` all pass: no null-data control and no BH oracle exists anywhere. A `bipolar_reference` sign flip and removal of `laplacian_reference`'s un-permute both pass. `tests/test_gpu_pca.py`'s "numpy reference" is a line-by-line copy of the implementation's own `_svd_numpy` branch, and all three tests pass `device="cpu"`, so the GPU branch has zero coverage.
- **Change** Add a lagged-pair positive control with an independent cross-spectral oracle for `imaginary_coherency` (clone `test_wpli_matches_an_independent_oracle`); seeded null cases asserting `p > 0.2` for the statistics group; one hardcoded BH oracle; a pinned sign for the referencing functions.
- **Preserves** Existing tests.
- **Discriminator** Each new test fails under the stated mutation.
- **Accept** No estimator in sections 1-2 survives its own mutation.

### 05-55 Test names that overclaim, and one that lets a missing dependency pass as a calibration failure
- **Problem** Bodies narrower than their names.
- **Evidence** `test_readme_quickstart_blocks_execute` never opens `README.md` — the `README` constant is unused in the function — and has already drifted: README line 96 says `t0_bounds=(0.0, 200.0)`, the test says `(0.0, 250.0)`. `test_readme_python_version_matches_policy` asserts the literals `"3.12"` and `"3.14"` and never reads `pyproject.toml`. `test_no_routed_module_probes_with_a_bare_cupy_import` searches only for `torch.cuda.is_available()`. `test_gpu_pca_cpu_and_cuda_agree_within_float32` has no GPU branch, so it compares CPU to CPU and reports PASS. `test_rsa_oracle`'s "SciPy oracle" tests call the identical SciPy function the implementation calls. `test_xflip_calibration`'s three FPR tests all pass with the surrogate gate removed entirely. `test_the_documented_centre_shrinkage_is_the_measured_one` hardcodes `0.6..0.95` while the receipt records 0.804 and the code gives 0.778. `test_onset_fitting.py:91` allows +/-60 ms where the measured error is 3.57 ms. Two `test_release_recovery_gates` tests patch `statsmodels` without importing it defensively, so a missing hard dependency surfaces as `ModuleNotFoundError` inside a mock.
- **Change** Repair each name-body mismatch; add `pytest.importorskip("statsmodels")` where a test patches it; tighten the onset tolerance to 15 ms.
- **Preserves** Coverage.
- **Discriminator** Each fails under the defect its name describes.
- **Accept** No test name asserts more than its body checks.

### 05-56 The vflip receipt hashes only part of what it certifies
- **Problem** `estimator_sha256` hashes `getsource(vflip)` alone, while `vflip` calls `_unit_range`, `_from_lfp` and `_device`.
- **Evidence** A line-count-preserving `_unit_range` mutation reintroducing the 0.2.4 centring defect (median bias +1.45 -> +6.66) leaves the receipt reading "current" and the file passing 4/4.
- **Change** Hash the closure, not the function; `scripts/calibrate_vflip.py:84`.
- **Preserves** The receipt format.
- **Discriminator** A helper mutation invalidates the receipt.
- **Accept** Mutating any function `vflip` calls fails `test_vflip_calibration_receipt`.

### 05-57 A test rewrites a tracked source file and leaks an environment variable
- **Problem** `tests/test_mcp_server.py:138` rewrites `jnwb/mcp_server/custom_tools.py`, a tracked file, restoring in `finally`; and line 2 sets `os.environ["ALLOW_DYNAMIC_TOOLS"]="1"` at import, process-wide.
- **Evidence** A kill or timeout leaves the tree dirty; `pytest-xdist` is declared, so two workers would race on one file.
- **Change** Write to `tmp_path`; set the variable with `monkeypatch.setenv`.
- **Preserves** The coverage.
- **Discriminator** `git status` is clean after an interrupted run.
- **Accept** No test writes inside `jnwb/`.

### 05-58 The suite spends 105 s on a 9.54 GiB fixture that carries no extra failure class
- **Problem** `tests/test_analyzers_coverage.py:27` allocates `np.random.randn(128,200,500,100)`.
- **Evidence** 27 s per test, 3 tests. At `(2,200,2,2)` (12.8 KiB) the mutation profile is byte-identical across four mutants; only the frequency axis is load-bearing. Verified on a copy: 3.09 s against 100.53 s, same 25 test ids, same outcomes. Lines 51 (1.14 GiB) and 270 (0.24 GiB) are the same pattern. Full suite is 383 s.
- **Change** Shrink the fixtures to the dimensions that discriminate.
- **Preserves** The 25 test ids and their outcomes.
- **Discriminator** The same mutants are caught.
- **Accept** About 27% of suite wall time recovered with no coverage loss.

### 05-59 Removable and mergeable tests
- **Problem** Tests that cannot fail, or duplicate another's failure class.
- **Evidence** `tests/test_rsa.py` in full (every failure class is covered by `test_rsa_oracle.py`; under a `pdist**2` mutation it caught nothing). `test_jnwb_frozen_boundary::test_jnwb_all_symbols_resolve` duplicates `test_api_surface::test_public_exports_resolve`. `test_addressing::test_area_resolution_is_identical_with_and_without_omission_importable` spawns two subprocesses and compares jnwb to itself, since the module is importable in neither arm; its own comment predicts this. `test_paths.py:93` puts `Path.cwd()` on both sides; `:173` restates the expression it checks. `test_spectral.py:901` instruments a `curve_fit` mock that is never invoked (`{'polyfit': 2, 'curve_fit': 0}`), so both halves test one path. `tests/test_parallel.py::TestParallelMap` spends 18.45 s squaring at most 100 integers.
- **Change** Delete the named tests; merge the seven `TestPublicImport`-style tests into one parametrized surface test and `TestHarnessResetContracts`' nine substring assertions into one.
- **Preserves** Every failure class.
- **Discriminator** The mutation set caught before and after is identical.
- **Accept** Deletion justified per test by the mutation it still catches elsewhere.

### 05-60 The two carried-forward 0.2.4 items
- **Problem** A receipt with no generator, and a test that cannot measure what it is named for.
- **Evidence** `artifacts/benchmarks/xflip_calibration_0.2.3.md` has no generator script. `tests/test_xflip_calibration.py` rebinds all four null families and three alternative categories to the shipped estimator, but runs 15 seeds against the document's 30 — and `assert fpr <= 0.05` at n=15 is satisfiable only by 0/15 — and has no analogue for the document's within-correlation sweep at rw = 0.2, 0.4, 0.8, nor for its localization-error columns. `test_frequency_grid_resolution_invariance` uses a noise-free PSD, so it cannot measure a null's grid dependence.
- **Change** Write the generator or retire the document in favour of the test, stating which operating points the test does not cover; give the grid-invariance test a noisy PSD. 05-07 is now closed: the gradient gate applies on both paths (FPR 0/15 on the graded null at both settings, true-positive 10/10 at within_corr 0.6 and 0.4), so the document's null rates must be re-measured or restated as conditional on neither setting rather than on `contiguous=True`.
- **Preserves** The measured operating characteristics.
- **Discriminator** The retained artefact is reproducible from a script in the repository.
- **Accept** No calibration receipt exists without a generator. Sequence after 05-07, which changes what is being calibrated.

## 9. Documentation

### 09 note: the persona is a neuroscientist who knows `pynwb` and nothing else, going install -> inspect their own file -> select data explicitly -> analyze -> interpret, without reading contributor material.

### 05-61 Six documented calls do not run
- **Problem** Signatures and call shapes that drifted.
- **Evidence** `docs/05:78` `repair_lfp_trials(..., window_ms=)` -> `TypeError: unexpected keyword argument 'window_ms'` (live: `exclude_window_ms`). `docs/05:49` `bad_trials_single_channel(..., r_thresh=0.2)` -> unexpected keyword (live: `corr_z_thresh=5.0`, a z-score not a raw correlation). `docs/06:33` `compute_response_metrics(..., event_onsets=)` -> "Did you mean 'epoch_onsets'?". `docs/06:33` `classify_response_significance(spike_times=..., alpha=0.01)` -> unexpected keyword; live it takes `(metrics: Dict[str,float], zscore_threshold, min_spike_count)`, i.e. the output of the previous call — the composition the page exists to teach, taught backwards. `docs/09:39` `assign_outer_folds(labels, n_splits=5, groups=)` -> live takes a DataFrame. `docs/09:39` `build_representation_ladder(X, labels, feature_names=)` -> live takes `(raster, *, modality, spatial_axis_metadata)` and `labels` is not an input. `docs/11` section 9.2 documents `zflip` with `phase_gradient` and `wpli_profile` fields that do not exist, contradicting the correct contract at `docs/02:128`.
- **Change** Fix each against the live signature.
- **Preserves** The pedagogy.
- **Discriminator** Every documented snippet runs.
- **Accept** A test extracts and executes every runnable fenced block, with CWD outside the checkout. Today only 1 of README's 4 python blocks is executed by any test.

### 05-62 The executable quickstart is not executable, and the README prints a fabricated onset
- **Problem** One script died to a tightened validation; one example has no signal to recover.
- **Evidence** `examples/quickstart_jnwb.py:126` raises `ValueError: scheme='within_group' has no exchangeability for this design` — the panel deliberately builds a constant-within-group label to demonstrate that the null cannot move, and the library now refuses to produce it. Both README and `docs/quickstart.md:54` call the script "executable", and `examples/figures/jnwb_quickstart.png` is its stale output. Separately, README's arrays quickstart runs and prints `Onset t0: 165.0 ms (R2=-0.00, None)` from `rng.uniform(0.0, 10.0, 300)`, homogeneous noise with no onset, with `bound_status` of `None` displayed as a status.
- **Change** Catch the refusal in the panel and plot it as the result, which is the lesson; inject a real onset into the README example or print the refusal when `r2` shows the fit is unusable.
- **Preserves** Both narratives.
- **Discriminator** The script exits 0; the README example reports a number it actually recovered.
- **Accept** `examples/quickstart_jnwb.py` runs in CI. It is currently executed by nothing.

### 05-63 The only runnable instruction on ten pages needs files that ship in neither artifact
- **Problem** `examples/` is in neither the wheel (`include = ["jnwb*"]`) nor the sdist (not in `MANIFEST.in`), yet `python examples/tutorials/NN_*.py` is the sole runnable line on `quickstart.md` and all nine tutorial pages, and `install.md` never says a clone is required.
- **Evidence** Wheel 53 entries, sdist 100 entries, `examples/` absent from both.
- **Change** One line in `install.md` and `quickstart.md` saying the tutorials require a clone. `docs/agents.md:14` already does this correctly for `AGENTS.md` and `skills/`.
- **Preserves** The tutorials as CI-executed pedagogy, which is the right place for them.
- **Discriminator** A `pip install` user is told what they do and do not have.
- **Accept** Every runnable instruction states its prerequisite.

### 05-64 Contributor material on the user-facing path, and one page that is a pointer
- **Problem** About 3,900 of 22,181 words (17.6%) address contributors from the nav.
- **Evidence** `docs/10_extending_jnwb_and_verification.md` (117 words) says "This page is a short pointer"; three of its four blocks duplicate `CONTRIBUTING.md`'s "Before you push", and its unique MCP line points at `agents.md`. That duplication already produced a stale fact: it says "gates 1-12" while the runner prints 13 and `CONTRIBUTING.md:57` says 13. `docs/11` (2,764 words) is contributor material under a "Tutorials & Development" heading, with sections 4, 5, 6 and 8 restating `CONTRIBUTING.md` near-verbatim and cross-referencing it circularly — but its section 9.2 (1,431 words) is the only documentation anywhere for `aperiodic_fit`, `vflip`, `xflip`, `zflip`, `probe_geometry`, `stream_npz_array` and `label_layers`. `docs/01` sections 1-3 name an internal scaffolding marker and a test file. The "logarithm last" rule appears four times in about 400 words. `api.md` is listed twice in the nav (28 entries, 27 unique).
- **Change** Delete `docs/10` and its nav entry; promote `docs/11` section 9.2 to a real page and move the rest to `CONTRIBUTING.md`; cut `docs/01` sections 1-3 keeping section 2C, the only statement of the causal-verb rule; keep one canonical statement of the logarithm rule in `common_mistakes.md` and link to it; drop the duplicate `api.md` nav entry.
- **Preserves** Every user-facing fact, including all of 9.2.
- **Discriminator** No page on the user nav addresses contributors.
- **Accept** Strict build clean; no orphan pages and no dead nav entries, both currently true.

### 05-65 Numbers are produced without saying what they license, and without units
- **Problem** Pages print an estimate and stop.
- **Evidence** `docs/02` prints `zflip`'s `directionality`, `tau_per_channel_s` and `apparent_velocity_m_s` with "propagation latency" framing and no note that apparent phase velocity is not conduction velocity — contradicting `AGENTS.md` section 5 and `docs/01` section 2C. `docs/07` prints a cluster-mass p with no statement that a significant cluster licenses "the conditions differ somewhere in the window" and not its onset, offset, peak or extent, and computes `cross_modal_comparison`'s `lag_ms` on white noise with no sign convention given. `docs/09` claims its fold partitioning prevents temporal-autocorrelation leakage and then shows `nested_cv_linear_svm(X, labels, n_splits=5)` with no `groups`. `docs/04` hands over `tfr_res.coi_mask` as a field name, never explaining edge contamination or that masking must precede any average, and never states the CSD sign convention, which is the interpretation. `docs/08` never states bits versus nats for TE or MI. `docs/tutorials/03, 04, 05, 06, 08` contain no unit token at all.
- **Change** One interpretation sentence per produced number; units at the point of production.
- **Preserves** The analyses.
- **Discriminator** Every page that prints a number says what it does not license.
- **Accept** Reviewed against `docs/common_mistakes.md`, which already holds most of these rules.

### 05-66 README links are dead on PyPI
- **Problem** `readme = "README.md"` makes it the long description, and PyPI does not rewrite relative links.
- **Evidence** `README.md:130,132,136` link to `CONTRIBUTING.md`, `artifacts/todo_stack.md`, `AGENTS.md` and `LICENSE`; `artifacts/` is additionally pruned from the sdist.
- **Change** Absolutise to `https://github.com/HNXJ/jnwb/blob/main/...`.
- **Preserves** In-repo navigation.
- **Discriminator** Every README link resolves from the PyPI page.
- **Accept** Checked against the rendered long description. Also delete the dangling `examples/quickstart_jnwb.py:17` pointer to an `omission/` example project that is not in this repository.

## 10. Skills and agents

### 05-67 Six routing rows teach a signature the code does not have, and one flips a sign
- **Problem** Rows carry hardcoded signatures with no process keeping them true.
- **Evidence** `skills/jnwb-statistics/SKILL.md:18` gives `paired_fire_prob_test(fires_null, fires_target, n_bootstrap=1000, rng=...)`; live is `(fires_target, fires_null, n_shuffles, n_bootstrap, rng)`. On one dataset the correct order gives `risk_difference = +0.6` and the skill's order gives **-0.6**, with no error — and the skill omits the required `n_shuffles`. `jnwb-lfp-spectral:32` tells the reader to inspect `frac_flagged` to bound median substitution; the real key is `max_fraction_trials_flagged_at_a_sample`, so `info.get('frac_flagged', 0)` silently skips the check. `jnwb-nwb-data:29` calls `epoch_continuous(data, onsets, win_s, fs)` positionally against a keyword-only signature. `jnwb-population:13` gives `nested_cv_linear_svm(..., n_splits=5)`; there is no default. `jnwb-lfp-spectral:14` shows `band_power(..., normalize=False)` as the signature; the default is `True`, which raises without a baseline. `jnwb-lfp-spectral:22` describes `cross_area_coherence` as working "across channel pairs"; 2-D input is refused by design.
- **Change** Correct all six against the live signatures.
- **Preserves** The routing structure, which is sound.
- **Discriminator** Each row executes as written.
- **Accept** Gated by 05-68.

### 05-68 The test that exists to catch 05-67 checks only that parameter names exist
- **Problem** `test_skill_routing_parameter_names_match_runtime` asserts `pname in sig.parameters` and nothing about order, required-ness, defaults or keyword-only markers; and its regex cannot span nested parentheses.
- **Evidence** Reconstructing the `paired_fire_prob_test` row, all four named parameters are present, so the test passes despite the swapped order and the missing required argument. The regex silently skips 7 of 61 routing rows, every one with a tuple default: `apply_tight_auto_axis`, `save_figure_suite`, `imaginary_coherency`, `wpli`, `zflip`, `spectral_tilt`, `assign_outer_folds`. Suite: 28 passed.
- **Change** Match parameters positionally against `sig.parameters` order, assert every required parameter appears, compare stated defaults to live ones, and balance parentheses in the regex; `tests/test_skills_validation.py:112`.
- **Preserves** The existing checks.
- **Discriminator** Reintroducing any of the six 05-67 rows fails the suite.
- **Accept** All 61 rows are checked, none skipped.

### 05-69 `AGENTS.md` has no rule keeping skills in sync, and three of its own statements are stale
- **Problem** Section 8 requires a public API change to update `CHANGELOG.md` with a deprecation path; nothing requires updating `skills/`, although skills hardcode signatures in 61 rows. That single gap produced every item in 05-67.
- **Evidence** Section 10 asserts "Each call below runs as written on synthetic arrays"; `aggregate_to_db(beta_raw, baseline_raw, how="mean_of_ratios", aggregate_over=0)` raises `AxisError: axis 0 is out of bounds for array of dimension 0`, because `band_power` returns a float — so the canonical demonstration of the repo's most-repeated safeguard does not run. Section 4.3 points at "the non-blocking scan item in the todo stack", which does not exist. Section 10's statistics entry point is `StatisticalAnalysis.exploratory_compare` while `skills/jnwb-statistics:13` routes to `compare_groups`; both exist and their return keys differ.
- **Change** Add to section 8: a public API change updates the routing rows in `skills/` in the same commit. Fix the recipe to build a per-trial array before `aggregate_over=0`. Remove the dangling pointer. Pick one comparison entry point.
- **Preserves** Everything else in `AGENTS.md`.
- **Discriminator** Section 10 executes end to end.
- **Accept** A test executes every fenced block in `AGENTS.md`, and resolves every path and section it cites.

### 05-70 An entire subsystem and three function families are unrouted
- **Problem** Skills predate parts of the API.
- **Evidence** No skill mentions `vflip`, `vflip_from_lfp`, `xflip`, `label_layers`, `current_source_density_1d`, `voltage_curvature_1d`, `VFlipResult` or `XFlipResult`, while `zflip` sits in lfp-spectral and `probe_geometry` in nwb-data; probes for "assign cortical layers" and "compute CSD" match no trigger. `cluster_permutation_test` appears in no routing matrix. `spike_mutual_information`, `spike_count_mutual_information`, `binary_occupancy_mutual_information` and `cross_modal_comparison` are unmentioned — and the last deliberately crosses modalities, which interacts with the router's "never pool across modalities" rule with no guidance either way. `bin_spikes`, `fires_in_window`, `rate_in_window` and `fire_indicator`, the half-open-bin family whose purpose is preventing the double-count in `common_mistakes.md` section 2, are unmentioned in the skill that owns binning.
- **Change** Add a `jnwb-laminar` skill owning the depth estimators, or a laminar section plus a router line; route the other three families.
- **Preserves** Exactly one canonical skill tree at `skills/`.
- **Discriminator** Every public symbol is reachable from a routing row or is deliberately out of scope.
- **Accept** Currently 84 of 151 symbols are mentioned by no skill; that set is reviewed and justified.

### 05-71 One skill overclaims a safeguard the router and `AGENTS.md` both state correctly
- **Problem** `skills/jnwb-lfp-spectral/SKILL.md:23` calls `imaginary_coherency` "volume-conduction-robust", while the router section 4.8 and `AGENTS.md` section 5 both say these measures "reduce sensitivity specifically to zero-phase-lag coupling; they do not establish immunity". Its neighbouring `wpli` row uses the correct phrasing.
- **Evidence** Same file, adjacent lines.
- **Change** Match the `wpli` row. Also add the narrowband PSI exclusion: the connectivity skill's own verification instruction ("verify PSI returns positive slope for driver") fails on narrowband — a 20 Hz sinusoid with 10 ms delay over a 19-21 Hz band gives `net=0.0000, sd=0.0, n_freq_bins=3, z=1.07e8`, while the same delay over 15-30 Hz gives 0.9161. And add the group-delay caveat to `jnwb-spiking`: it mandates `causal_exp_smooth` for latency without stating that the filter shifts onset by about 0.7*tau (measured: tau=25 gives +10 ms, tau=50 gives +30 ms), which `common_mistakes.md` section 8 documents and no skill repeats.
- **Preserves** The safeguards, which are otherwise the tree's best asset.
- **Discriminator** No skill states a stronger claim than the router.
- **Accept** Cross-checked against `AGENTS.md` section 5 and `docs/common_mistakes.md`.

### 05-72 The MCP server has a fourth tool that writes code, is undocumented, and never loads
- **Problem** `docs/agents.md:24` says "Three tools, all of them ingest"; `mcp.list_tools()` returns four.
- **Evidence** `['inspect_nwb', 'prepare_signal_reference', 'get_event_codes_and_timings', 'add_tool']`. `add_tool(code)` writes Python source into the installed package directory, gated only by `ALLOW_DYNAMIC_TOOLS=1`, and appends to `custom_tools.py` — which `jnwb/mcp_server/__init__.py` does not import, so its "Please restart the MCP server to load the new tool" message is false at any restart. `docs/10:18` gives a third number by pointing at `jnwb.mcp_server.__all__`, which has five entries.
- **Change** Decide whether `add_tool` ships. If it does: document it and its env gate, and wire `custom_tools` into `__init__.py` so the message is true. If not: drop it from `__init__.py`. Point every count at the live registry rather than restating it.
- **Preserves** The three ingest tools.
- **Discriminator** The documented tool list equals `mcp.list_tools()`.
- **Accept** A test compares the documented table against the live registry. Ruled 2026-09-16: resolve from evidence, not by asking. Inspect `add_tool` for mutation scope, input validation, security boundary and overlap with the other three tools. Keep it, wire `custom_tools` in and document four tools only if it is a distinct, safe, generic operation genuinely intended for external agents; otherwise remove it from the exposed MCP surface and document three. Public exposure requires intent, and the live implementation -- not the stale docs -- is the authority on what it does.

## 11. Packaging

### 05-73 A build from `dev` today produces a different distribution calling itself 0.2.4
- **Problem** The version is not bumped after a release, and nothing compares the declared version against what the index already serves.
- **Evidence** HEAD is 5 commits past `v0.2.4` with `__version__ = '0.2.4'` and 20 non-empty lines under `## [Unreleased]` naming three shipped fixes. Local wheel against the PyPI wheel: `> jnwb/mcp_server/__main__.py`. Local sdist carries `AGENTS.md` and `skills/` (261,291 B) where PyPI's does not (238,292 B). `test_release_date_matches_the_changelog_entry_for_this_version` passes, because it compares the version to its own changelog entry and never to the index.
- **Change** Add a release-gate step: fail when `jnwb.__version__` already appears in the PyPI index and `CHANGELOG.md` has a non-empty `## [Unreleased]`.
- **Preserves** The existing version-sync gate 7.
- **Discriminator** The current tree fails the new check.
- **Accept** Two distributions can never share a version string.

### 05-74 Seven of ten dependency floors cannot be installed on any supported interpreter
- **Problem** Floors copied from an older support window and never re-derived after the 3.12 floor landed.
- **Evidence** PyPI metadata: `numpy==1.22.0` tags `['cp310','cp38','cp39','pp38','sdist']`; `scipy==1.8.0` declares `requires_python '>=3.8,<3.11'`, which contradicts `requires-python = ">=3.12"` outright; `pandas==1.4.0`, `h5py==3.6.0`, `matplotlib==3.5.0`, `scikit-learn==1.0.0`, `statsmodels==0.13.0` ship no cp312 or pure-python wheel. Separately `jnwb.statistics` and `jnwb.connectivity` call `scipy.stats.false_discovery_control`, added in SciPy 1.11, three minor versions above the declared floor — masked only because scipy <1.11 cannot install on 3.12.
- **Change** Raise each floor to the oldest release with a cp312 artifact, or delete the floors and state that the package takes whatever pip resolves on 3.12.
- **Preserves** Current resolutions, which are all far above the floors.
- **Discriminator** Every declared floor is installable on the declared interpreter.
- **Accept** `pip install 'numpy==<floor>'` succeeds on 3.12 for each dependency.

### 05-75 The forbidden-path check cannot see `tests/` or `scripts/` in the wheel
- **Problem** `forbidden = [..., '/tests/', '/scripts/']` substring-matched against archive entries whose delimiters differ by format.
- **Evidence** `'/tests/' in 'tests/__init__.py'` is False. Wheel entries have no leading component, so the check works only for the sdist, whose entries are `jnwb-0.2.4/tests/...`.
- **Change** Match on path components for the wheel; keep the substring form for the sdist; `workflow.yml:89`, `release_gate.py:178`.
- **Preserves** The sdist check.
- **Discriminator** A wheel containing a top-level `tests` package fails.
- **Accept** Verified by constructing such a wheel in a scratch directory.

### 05-76 CI never runs the suite against the installed distribution
- **Problem** `pytest -v tests/` runs from the checkout root and `pythonpath = ["."]` puts the checkout ahead of site-packages, so the four-cell matrix tests the source tree that also happens to have the package installed. Only the single-cell build job touches the wheel.
- **Evidence** `workflow.yml:49`, `pyproject.toml:107`. Several test docstrings reason about wheel behaviour while importing the checkout.
- **Change** One matrix leg, or one extra step, that installs the built wheel and runs pytest from a directory outside the checkout with `pythonpath` overridden.
- **Preserves** The existing legs, which need `pythonpath` for the `scripts.*` gate tests.
- **Discriminator** A defect present only in the packaged artifact fails CI.
- **Accept** The claim "tested against the installed wheel" becomes true for the suite, not only for the tutorials.

### 05-77 The skills distribution decision
- **Problem** `MANIFEST.in`'s comment describes an outcome its mechanism does not produce.
- **Evidence** `graft skills` places the tree at the sdist root, outside any package; `packages.find` is `include = ["jnwb*"]`, so `pip install jnwb-0.2.4.tar.gz` installs `jnwb/` and discards `skills/` and `AGENTS.md`. Only someone who untars by hand receives them — and the sdist carries no `docs/`, `tests/` or `scripts/`, so 11 of 12 skill documentation links dangle inside it and the skills' own verification steps cannot run there. `grep -rn "skills" jnwb/ --include=*.py` returns zero hits: nothing in the runtime reads them.
- **Change** Recommendation from the packaging audit, for a ruling: keep `skills/` in the sdist as source, correct the `MANIFEST.in` comment to say what it does, and do not put the tree in the wheel — the consumer is a harness configured by path, not the Python runtime, and `site-packages` is the worst place to put something that must be pointed at. Close the discovery gap instead with a machine-readable pointer (a `jnwb.SKILLS_URL` constant naming the GitHub tree). The `importlib.resources` and console-entry-point routes both require the tree inside the wheel, which is the second tree gate 2 forbids.
- **Preserves** Exactly one canonical skill tree.
- **Discriminator** A `pip install` user can find the skills without guessing.
- **Accept** Ruled 2026-09-16, as recommended: one canonical tree in the repository; ship `skills/` in the sdist where appropriate; do **not** create a duplicate `jnwb/.../skills` tree to force them into the wheel. Wheel runtime resources carry skills only if a runtime loader needs them, and none does -- `grep -rn "skills" jnwb/ --include=*.py` returns nothing. Packaging symmetry is not an objective. Correct the `MANIFEST.in` comment to describe what its mechanism actually does, and close the discovery gap with a machine-readable pointer. This closes the open half of the carried-forward 05-02.

### 05-78 Declared test tooling that is never invoked, and a second source of truth for the docs pins
- **Problem** Unused declarations and duplicated configuration.
- **Evidence** `pytest-cov` and `pytest-xdist` are declared, and the `test` extra pulls `pytest-cov-7.1.0`, `coverage-7.16.1`, `pytest-xdist-3.8.0` and `execnet-2.1.2` onto all four CI cells; there is no `addopts`, no `--cov` and no `-n` anywhere in the repository. `.readthedocs.yaml` installs both `docs/requirements.txt` and `.[docs]`; the two lists are byte-identical today and nothing compares them, while `fail_on_warning: true` means a drift is a failed publish. Also: `scripts/build_unified_review.py` and `scripts/reconcile_review_probes.py` have zero references anywhere (625 lines), and `harness_gate.py:205` holds a root-allowlist exemption for `jnwb-unified-rev.md`, the output of the first of them.
- **Change** Drop both pytest plugins or make the declaration true with an `addopts`; delete `docs/requirements.txt` and its `.readthedocs.yaml` entry; retire both dead scripts and the allowlist entry.
- **Preserves** Every live script: `docs_build`, `generate_api_md`, `harness_gate`, `release_gate`, `calibrate_vflip`, `mkdocs_version_hook`, `benchmark_import`.
- **Discriminator** Every declared dependency and every script has a caller.
- **Accept** All six extras resolve (verified: `mcp` 24, `torch` 9, `gpu` 6, `test` 78, `docs` 25, `all` 107 packages, all exit 0, `all` an exact union). Note `jnwb[gpu]` installs cleanly with no CUDA and yields no GPU, because plain `jax`/`jaxlib` from PyPI is CPU-only: it should be `jax[cuda12]`.

## 12. Harness and gates

### 05-79 Nine of thirteen gates can pass on a broken tree
- **Problem** Presence and substring checks standing in for behaviour.
- **Evidence, each reproduced** Gate 11: a root directory containing `.py` files and no `__init__.py` is importable as a PEP 420 namespace package and is not flagged, so JNWB-002 reproduces green; `test_non_package_directory_is_not_flagged` locks the hole in. Gate 13: a README stating the three symbols are REMOVED, all nine tutorials raising `SystemExit`, and a commented-out mkdocs nav line all pass. Gate 5: satisfied by `docs/api.md`, which is generated from `__all__` — it cannot fail while gate 9 passes, and substring matching means short names match inside longer ones. Gate 7: a `pyproject.toml` whose `attr` binding sits inside a comment, plus `version = "0.0.1"`, passes. Gate 8: every block is guarded by `if <file>.exists():` with no `else`, so an empty directory passes the Python-policy gate; and `PYTHON_CI_REQUIRED` omits 3.13 while the gate prints "all agree" for a classifier set that includes it. Gate 3: the drive-letter allowlist does not include `E:/`, which is in use on this machine. Gate 2: checks one hardcoded path, so a duplicate tree at `jnwb/skills/` or `docs/skills/` passes. Gate 4: the allowlist carries four entries that do not exist. Gates 5, 10 and `test_docs_links` all use non-recursive `glob("*.md")` and therefore miss the same nine live files under `docs/tutorials/` — reproduced by planting `jnwb==0.0.9` there.
- **Change** Gate 11 -> `find_spec`. Gate 13 -> parse the mkdocs YAML and `compile()` each tutorial, or demote it. Gate 5 -> retire, subsumed by gate 9, and replace with the check 05-41 needs: every `__all__` symbol mentioned outside the generated reference. Gate 7 -> parse with `tomllib`. Gate 8 -> add `else: violations.append(...)` three times, and either test 3.13 or change the PASS string. Gate 3 -> match `^[A-Za-z]:[\\/]`. Gate 2 -> glob `**/SKILL.md` and assert every hit is under `skills/`. Gate 4 -> prune the four stale entries. Three `glob` -> `rglob`.
- **Preserves** Gates 1, 6, 9 and 12, which are behavioural and well-documented.
- **Discriminator** Each repaired gate fails the adversarial tree that currently passes it.
- **Accept** `tests/test_harness_adversarial_gates.py` gains one constructed-input probe per repaired gate. Its `TestGateNumberingIntegrity` machinery is the right model. Also wire the four checks that ship but never run: `check_protected_paths` (all three paths missing), `validate_receipt_provenance`, `check_logarithm_last_rule`, `check_modality_isolation`.

### 05-80 Nothing enforces the todo-stack rule or resolves `AGENTS.md`'s own pointers
- **Problem** `AGENTS.md` section 2 states the stack holds only work not yet done; no gate or test checks it, which is why the stack accumulated a completed-work table, and no check resolves the file's own references, which is why section 4.3 points at a deleted item.
- **Evidence** `grep -rn "todo_stack" scripts/ tests/` returns one hit, a path string. The stale pointer is confirmed by `grep -in "non-blocking" artifacts/todo_stack.md` returning nothing.
- **Change** A test that resolves every path, test name and section reference in `AGENTS.md` and both stacks, and asserts the stack carries no "CLOSED"/"DONE" markers.
- **Preserves** Both stacks' formats.
- **Discriminator** Reintroducing a dangling pointer fails the suite.
- **Accept** The registry-staleness class that produced this item is mechanically prevented.

### 05-81 `scripts/harness_gate.py` and `scripts/mkdocs_version_hook.py` describe themselves wrongly
- **Problem** Module docstrings drifted from the code.
- **Evidence** `harness_gate.py`'s docstring lists gates 1-12; the runner prints 13. `mkdocs_version_hook.py:12` says "the package pins >=3.12,<3.13", while `pyproject.toml:17` is `>=3.12` and `harness_gate.py:493` fails the build on any `<` in that spec — so the comment cites the exact upper pin the harness exists to forbid. `connectivity.py:16` claims "Residual variance uses explicit N - p divisors" while `_residual_variance` ignores its `n_params` argument and returns RSS/N. `artifact_detection.py:93` documents returns as `(flag, corr_summary, amp_per_trial)` while the code returns z-scores (measured: `third[7] = 332.40` against a true `max|amp|` of 54.21). `tfr_accumulator.py:1` promises float64/complex128 accumulation; the persisted dtypes are float32/complex64.
- **Change** Correct each docstring; drop the dead `n_params`.
- **Preserves** Behaviour.
- **Discriminator** `test_docstring_matches_the_globs_it_claims`, which already exists for gate 6, is generalised.
- **Accept** No module docstring contradicts its code.

### 05-82 CI hygiene
- **Problem** Three small gaps on a publish-capable pipeline.
- **Evidence** No workflow-level `concurrency:` or `permissions:`, so rapid pushes run overlapping publish-capable pipelines. `pypa/gh-action-pypi-publish@release/v1` is a mutable branch ref on the two jobs holding `id-token: write`. `workflow_dispatch.inputs.target` defaults to `testpypi`, so any manual dispatch publishes unless the operator picks `none`. Confirmed clean: no `continue-on-error`, no `|| true`, no `set +e` anywhere; `if-no-files-found: error` is set; the production PyPI trigger is correctly narrow.
- **Change** Add `concurrency` and a `permissions: {contents: read}` floor; pin the publish action to a commit SHA with a version comment; flip the dispatch default to `none`.
- **Preserves** The publication ordering in `artifacts/fact_stack.md`.
- **Discriminator** A second push cancels the first; a manual dispatch publishes nothing by default.
- **Accept** `tests/test_workflow_release_policy.py` extended to cover the dispatch default.

## 13. Close-out

### 05-83 Independent adversarial pass over the repaired tree
- **Problem** The repairs above touch every subsystem and several change what other items calibrate.
- **Change** One independent pass attempting to falsify: numerical correctness, failure semantics, API consistency, docs, skills, packaging, CI and gate efficacy — reproducing each finding before repairing it, as the 0.2.4 pass did.
- **Preserves** Nothing by assumption.
- **Discriminator** Findings are reproduced before repair and pinned by a test that fails the previous code.
- **Accept** Every major finding either repaired with a failing-before test or recorded as triaged with its measurement.

### 05-84 Release seal
- **Problem** 0.2.5 is not releasable until the above is closed.
- **Change** Bump version, release date and status; write the CHANGELOG; clean tree; push `dev`; remote CI green on the full matrix; merge per the ordering in `artifacts/fact_stack.md`; tag; release; verify from the published artifact rather than a local build.
- **Preserves** Release publication ordering: validate on `main`, tag, GitHub Release, production PyPI.
- **Discriminator** A fresh venv installs from PyPI and reproduces the version, status, release date and full symbol set.
- **Accept** Verified from PyPI, not from a local wheel or cache.

# Before 1.0

- Replace example-based estimator coverage with analytic or property-based tests.
- Processing-module discovery generalization beyond LFP if a corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.

# Environment note, not repository work

The development virtualenv at `.venv` has `omission` editable-installed
(`__editable__.omission-0.1.0.pth`) and jnwb not installed (`pip show jnwb` -> not found), and
is missing `statsmodels`, a declared hard dependency, plus `mkdocs` and `nbclient`. Every local
receipt is therefore taken in an environment the boundary gates would reject, and 7 of the
1472 local test failures trace to it while CI is green. This is machine configuration, not a
repository change.
