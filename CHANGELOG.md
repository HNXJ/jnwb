# Changelog

All notable changes to `jnwb` will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Five copies of the dict-access shim became one `jnwb._dictlike.DictAccessMixin`.**
  The five classes above now declare the mixin instead of each carrying the pair, so the
  fix above landed once rather than five times. Read access only: these are records of a
  computation, not mappings to build, so there is no `__setitem__` and no iteration, and
  each class keeps its own `to_dict()`.
- **`_with_nwb` has one definition.** It was byte-identical in `jnwb/nwb_events.py` and
  `jnwb/nwb_inspect.py`, annotated with two aliases -- `NWBInput` and `InspectInput` --
  that spell the same type, over a `PathLike` that was also written out twice. All three
  names now live in `jnwb.nwb_io`, which both modules already imported `nwb_read_io`
  from. `jnwb.nwb_inspect.InspectInput` remains as an alias of `NWBInput`. The two
  module-local `PathLike` aliases are gone; `jnwb.nwb_io.PathLike` is the same type, and
  no importer of either copy exists anywhere in this repository or the workspace.
- **`channel_correlation_matrix` and `trial_correlation_matrix` share their body.** Both
  were `np.corrcoef(np.asarray(x, dtype=float))`; both now call one private
  `_pearson_rows`. Both public names are kept, because the difference between them is
  what a row means, not what is computed.
- **`tfr_dir`, `meta_dir` and `conndb_dir` share their body.** Three copies of the same
  six lines, differing only in which three constants they named, now pass those three
  constants to one `_configured_dir`. Each keeps its own docstring naming its own
  variables. Merging them exposed a gap: the documented order
  `override > $JNWB_*_DIR > $OMISSION_*_DIR (deprecated)` was tested for `nwb_dir`, which
  has its own body, but never for these three -- a mutation making the deprecated
  variable win passed the whole suite. It is tested now, for all three.
- **The `statistics.py` forwarders say which way they point.** `clopper_pearson`,
  `clopper_pearson_ci`, `mann_whitney_p_floor` and `exact_sign_flip` forward from
  `StatisticalAnalysis` to the module-level implementation; `fdr_correct` runs the other
  way, module to class. The direction could not be inferred from either side and is now
  stated in each summary. No delegation was redirected: changing one would move results
  for callers of the other spelling.
- **`CANONICAL_VFLIP_BANDS` is now the source of the bands, not a third copy of them.**
  The constant had no references, and deleting it would have been the wrong direction:
  the same two intervals were written out as literal defaults in `vflip` and
  `vflip_from_lfp`, so one fact was maintained in three places. The defaults now read
  from the constant. **No value changes** -- (8.0, 30.0) and (50.0, 150.0) either way --
  and the vFLIP calibration was rerun to prove it: the receipt's `estimator_sha256` moves
  because `vflip`'s source did, and every other field in
  `vflip_calibration_0.2.4_raw.json` is identical across 30 seeds, every null and
  alternative family, and every sweep.
- **`jrsa` no longer defaults to every core, which was making it slower.** It was the
  only public function in the package overriding `n_jobs`'s documented default of 1, and
  the override cost more than it bought: measured one call per interpreter on a 40x6
  input with the documented default of 1000 permutations, `jrsa(x1, x2)` ran 10x to 24x
  *slower* with `n_jobs=-1` than serial. The cause is not joblib. Starting 24 workers for
  a callable that closes over nothing takes 0.77 s; doing it for a callable the workers
  must import this package to unpickle takes 4.47 s, because each worker pays
  `import jnwb` -- 1.79 s in a fresh interpreter -- first. Every parallel call site in
  this library passes such a callable, so no small input can repay it, and the break-even
  is roughly five seconds of serial work rather than the one second `_parallel.py`
  claimed. A 400x60 input with 10000 permutations is past it: 10.8 s serial against 5.6 s
  on all cores. The default is now 1 everywhere, `jrsa` included; pass `n_jobs=-1` to opt
  in. **No number changes** -- `n_jobs` is a speed knob, and the statistic and p-value are
  bit-identical between the old default and the new one on identical input and `rng`.
  Benchmarks that call twice in one process will not reproduce the old cost, because the
  second call reuses the pool and takes about 0.04 s.
- **Gate 5 no longer counts the generated reference.** It searched every `docs/*.md`,
  `docs/api.md` included. Since `api.md` is generated from `jnwb.__all__`, the gate
  asserted that every export appears in a file guaranteed to contain every export: it
  could not fail, and it did not, while twelve symbols were documented nowhere a reader
  would look. It now excludes `api.md` and matches whole words, so a page that documents
  `AlignedDataset` is no longer credited with documenting `Dataset`.
- **`inspect` answers with one schema, whichever way it is called.** `inspect(path)` was
  an h5py walk and `inspect(nwb)` a pynwb walk, written independently, and for the same
  file they disagreed: the file form carried `data_path` and `layout` and the object form
  did not; an interval table had four columns from the file (`codes`, `id`, `start_time`,
  `stop_time`) and three from the object, because `to_dataframe()` makes `id` the index;
  and `codes` was dtype `object` from one and `str` from the other. An `NWBFile` that was
  read from a file is now described by that file, so passing an open handle -- the
  documented way to avoid reopening -- gives the same dict as passing the path. An
  `NWBFile` with no file behind it is described from its arrays in the same schema, and
  now includes its `trials`, `epochs` and `invalid_times` tables, which are not in
  `nwb.intervals` until the file has been written and read back. Every entry carries
  every key in `jnwb.nwb_inspect.CONTINUOUS_KEYS`, `None` where the value is unknown,
  rather than a key set that varied with the file's contents.
- **A continuous container holding several series is a question, not an answer.** An
  `LFP` container wrapping `lfp_alpha` (1000 Hz) and `lfp_beta` (500 Hz) now reports
  `series: ["lfp_alpha", "lfp_beta"]` with `rate_hz`, `data_path`, `data_shape`,
  `data_dtype` and `layout` all `None`, and `acquisition_channel(name="LFP")` raises
  `AmbiguousAcquisitionError` naming both. Name either series to read it. Containers
  wrapping exactly one series are unchanged.
- **A name that means two different objects is refused.** A series called `shared` in
  both `/acquisition` and a processing module resolved to the acquisition one, decided by
  the order of two `if` statements and documented nowhere. `resolve_acquisition` and
  `acquisition_channel` now raise `AmbiguousAcquisitionError` naming both locations.
- **`rng` is the one spelling for the random-number argument.** One concept was spelled
  four ways across the public API: `rng` (8 functions), `seed` (7), `random_state` (3) and
  `random_seed` (1). `granger`, `granger_spectral`, `phase_slope_index`,
  `transfer_entropy`, `zflip`, `cross_modal_comparison`, `build_permutation_plan`,
  `shuffle_r2_ci`, `resample_onsets` and `jrsa` now take `rng`. The old spelling remains
  as a keyword-only alias and still works; the canonical parameter keeps its original
  position, so positional callers are unaffected, and its original default, so no
  number moves. Passing two spellings with different values raises
  `ValueError: Conflicting values`, the same refusal `band_power(fs=, sampling_rate=)`
  already used -- `jrsa` previously spelled this refusal `TypeError`, and was the only
  place that did. `rng` is canonical rather than `seed` because the argument now accepts
  a `Generator`, which `seed` would misname.
- **`build_permutation_plan` refuses a `Generator` explicitly.** It is the one exception:
  its product is a manifest of integer per-draw seeds, `rng + i`, which a `Generator`
  cannot name and fresh entropy would make unreproducible. It now says so instead of
  failing on `seed + i` inside the loop.
- **`rng=None` now means fresh entropy, and the default seed is in the signature.**
  `exact_sign_flip`, `compare_groups`, `bootstrap_ci`, `permutation_test` and
  `_bootstrap_mean_diff_ci` declared `rng: Optional[Generator] = None` and then ran
  `np.random.default_rng(42)` when the caller omitted it; `cluster_permutation_test` used
  `default_rng(0)`. `None` reads as "fresh randomness", so two calls a caller believed
  were independent shared a null distribution and agreed exactly. The seed each function
  was already using is now its signature default -- 42, and 0 for
  `cluster_permutation_test`, whose different value is preserved because unifying it would
  change published cluster p-values. **Omitting `rng` produces exactly the numbers it
  produced before**; passing `rng=None` explicitly now draws fresh entropy, as it does
  everywhere else in NumPy.
- **`rng` accepts an int seed as well as a `Generator`.** These functions used to raise
  `TypeError` for `rng=42` while seeding themselves with 42 whenever the argument was
  omitted, and the module-level `exact_sign_flip` already accepted
  `int | Generator | None`, so siblings disagreed about the same argument. A value that
  names no stream -- a `str`, a `float`, a `bool` -- still raises, now naming the caller.

### Added

- **`Provenance` records the jnwb that ran, not the one the caller names.**
  `software_version` is a required caller argument and nothing derived it, so a record
  could name a version that never executed and, the dataclass being frozen, keep it
  faithfully. There was also no path, and a version cannot identify an implementation on
  its own: an editable install of a development tree and a release in `site-packages`
  report theirs the same way and are routinely different code. `jnwb_version` and
  `jnwb_path` are read from the executing package and are `init=False`, so a caller
  cannot pass them -- caller metadata supplements the observed identity and cannot
  override it. `software_version` stays, as the caller's own claim; when the two
  disagree, `version_claim_matches_execution` is False and the disagreement is in the
  record rather than behind it. Both new fields appear in `to_dict()`.

- **`docs/errors.md`: every refusal, what produced it, and the argument that resolves
  it.** Twelve exported error classes and the two NWB resolvers appeared on no
  hand-written page -- only in `docs/api.md`, which is generated from `jnwb.__all__` and
  so contains every export by construction. Nine of the twelve are the resolvers and the
  errors they raise, which is everything a reader meets on their first unfamiliar file.
  The page quotes the real messages, and a test asserts each quoted fragment is still a
  literal in `jnwb/*.py`, so it cannot drift into describing errors the code no longer
  produces. Linked from the index and the mkdocs nav.
- **`jnwb.DETECTION_TAILS` is explained** in `docs/05_artifact_detection_and_repair.md`,
  where the one-sided/two-sided choice it names is already discussed.
- **`nested_cv_linear_svm(..., rng=42)`.** The signature was `(X, labels, n_splits)` with
  `random_state=42` hardcoded at four sites, so partition sensitivity could not be
  assessed: there was no way to ask whether a decoding accuracy survived a different
  split of the same trials. An `int` is handed to scikit-learn unchanged, so the default
  reproduces the previous folds exactly.
- **`jnwb.AmbiguousLayoutError`.** Raised by `acquisition_channel` when the channel axis
  of a 2-D series cannot be determined, and reported by `inspect` as
  `layout: "ambiguous"`. A subclass of `NWBInspectError`, like the other inspection
  errors.

### Removed

- **Two `jrsa` helpers nothing reached.** `_confidence_interval`, an analytic normal
  approximation superseded by the percentile bootstrap that is the live path, and
  `_chunk_tensor` (see above). Both private.

### Deprecated

- **`jnwb.ontology.create_aligned_dataset`, `create_result` and `create_figure`.** Each
  forwards its arguments to the constructor of the same name and adds nothing:
  `create_result(q, s, p, l) == Result(q, s, p, l)` for every input, and
  `create_aligned_dataset` additionally duplicates `Dataset.with_alignment`. They were
  never in `ontology.__all__` or `jnwb.__all__`. Calling one now raises a
  `DeprecationWarning` naming the replacement; they will be removed in a future release.
  Call the dataclass directly. The other eleven ontology exports are retained.

### Fixed

- **The vFLIP calibration receipt certified one function of the estimator.**
  `estimator_sha256` hashed `inspect.getsource(vflip)`, while `vflip` delegates its band
  normalization to `_unit_range`. Recentring that helper on its own mean -- a
  line-count-preserving change that moved the median signed bias off-centre from +0.053
  to -0.123 contacts -- left the receipt reading "current" and
  `tests/test_vflip_calibration_receipt.py` passing 4 of 4. The hash now covers `vflip`
  and every module-level function in `jnwb.laminar` it can reach, resolved from the call
  graph rather than listed, so a helper added later is covered without anyone remembering
  to extend a list. The reachable set is recomputed in the test and compared against the
  set the generator hashes, so the receipt cannot quietly narrow again. Both mutations --
  the helper and `vflip`'s own source -- now fail the receipt test; the helper mutation
  previously survived it. Two of the three helpers the item named, `_from_lfp` and
  `_device`, are not module-level functions in `jnwb/laminar.py`; the closure is `vflip`
  and `_unit_range`. The receipt was regenerated rather than edited: of 12924 leaf values
  in the raw JSON, exactly one changed, the hash, which confirms the estimator is
  unchanged and the calibration is fully seeded.
- **Seven tests asserted less than their names claimed.** Each claim was reproduced
  before anything was changed, and each repair was then mutation-checked against the
  defect its name describes; all seven mutants were killed.
  `test_readme_quickstart_blocks_execute` held a hand-copied transcription and never
  opened `README.md` -- the module-level `README` constant was unused in the body -- so
  the two had already drifted, the README passing `t0_bounds=(0.0, 200.0)` where the copy
  asserted `(0.0, 250.0)`. It now executes the README's own fenced blocks, so there is no
  second copy to drift. `test_readme_python_version_matches_policy` asserted that the
  literals `"3.12"` and `"3.14"` appear somewhere in the README, which survives any change
  to `requires-python` or to the CI matrix; it now reads `pyproject.toml` and
  `.github/workflows/workflow.yml` and compares them against what the README states.
  `test_no_routed_module_probes_with_a_bare_cupy_import` searched only for
  `torch.cuda.is_available()`, so the bare cupy import named in its own docstring was the
  one case it could not report; it now checks both libraries by import across the routed
  modules, allowing `*_gpu` implementations, which run only after a caller has resolved.
  Three `rdm_similarity` tests compared the dispatcher against the same SciPy function it
  dispatches to; the coefficients are now computed from each estimator's definition.
  `test_the_documented_centre_shrinkage_is_the_measured_one` allowed a slope anywhere in
  `[0.60, 0.95]`, 3.8 times the estimator's measured spread and wide enough to admit the
  0.95 that the test's own docstring says must be reported; measured over five disjoint
  nine-seed sets the slope runs 0.7557 to 0.8487, and the band is now `[0.70, 0.90]`.
  `test_recovers_known_onset_within_tolerance` allowed +/-60 ms on a 50 ms onset, so a fit
  reporting 0 ms passed a test named for recovery; the error at this seed is 3.57 ms and
  the bound is now 8 ms.
- **xFLIP's surrogate significance test was gated by one test.** Removing the decision
  entirely -- `is_sig` unconditionally true whenever surrogates ran -- left three of the
  four false-positive-rate tests and all nine `TestXFlipGradientGateOnBothPaths` tests
  passing, because the contrast and boundary-drop gates reject those nulls without it.
  Only the AR-noise case noticed, and only as a rate. On correlated noise the other gates
  open and the surrogate test is the sole reason for rejection on 14 of 25 seeds, with
  omnibus p running to 0.56, so acceptance is now asserted to imply significance there,
  with a non-vacuity guard on how many such seeds occur.
- **Four estimators had no test that could tell them from a constant.** Each of the
  audit's nine candidates was run as a mutation against the whole suite before anything
  was changed, because "nothing catches this" is a claim about the suite, not about one
  file. Four mutations survived all 2391 tests: `imaginary_coherency` returning 0.0 for
  both `icoh_mean` and `icoh_abs_mean`, `paired_fire_prob_test` pinned to p = 0.0001,
  `confirmatory_compare` confirming everything, and `bipolar_reference` with its sign
  flipped. `imaginary_coherency` now has a positive control checked against an oracle
  that recomputes Im(coherency) from segment, detrend, window and rFFT, reusing no jnwb
  helper and no scipy spectral estimator; the two p-values are calibrated across 20 null
  draws in each direction, since one seed showing a large p-value is a draw rather than a
  property; and the referencing sign is pinned to an exact expected array. Separately,
  `tests/test_gpu_pca.py` compared the implementation against a line-for-line copy of its
  own `_svd_numpy` branch and compared with `abs(corr)`, which is sign-invariant, so
  `pin_component_signs` was uncovered too; it now checks against an eigendecomposition of
  the scatter matrix, asserts the documented sign convention directly, and exercises the
  CUDA fallback's control flow without a GPU. **No estimator changed.** All ten repairs
  are verified by mutation, including the reverse of each constant, so a test asserting
  "not significant" also rejects "always significant".
- **Four of the audit's nine claims did not reproduce and no code was changed for them.**
  Mutating both shuffle p-values to `1/(n+1)`, `shuffle_r2_ci.p_val` to 0.001,
  `fdr_correct` to return its input, and `laplacian_reference` to skip its un-permute all
  failed the existing suite. The catching tests are
  `test_api_consistency.py::TestAlternativeAndAlpha::test_case_and_whitespace_are_folded_not_ignored`,
  `test_independent_audit_semantics.py::TestMonteCarloPValueConvention::test_shuffle_r2_ci_uses_one_plus_k_over_b_plus_one`,
  `test_jrsa_correctness.py::TestMultipleCorrectionFallback::test_multiple_correction_bh_matches_fdr_correct`
  and `test_spectral.py::TestLaplacianReference::test_channel_order_un_permutes_back_to_input_positions`.
- **Four tests asserted things that could not be false.** `test_docs_nwb_workflow.py`
  asserted a token was absent from `re.findall` output, which returns match substrings
  that can never contain a longer string -- and the pattern had no `re.MULTILINE`, so the
  list was empty regardless. `test_representative_workflow.py`, whose own docstring calls
  it "the load-bearing assertion", blocked `omission` with a meta-path finder defining
  `find_module`, dropped from the protocol in 3.12: on 3.14.3 a `find_module` blocker
  imports the blocked module anyway, while a `find_spec` blocker raises. With the blocker
  made live, the workflow still runs without `omission`, so the claim was true and simply
  untested. `test_jnwb_frozen_boundary.py` iterates `AUTHORIZED_EXCEPTIONS`, which is
  `set()`; the loop is correct and stays, and the detector it depends on is now exercised
  directly, so the first exception added is checked by code known to work. Three tests in
  `test_jnwb_core.py` kept their assertions behind `if 'error' not in result:`: replacing
  all 14 public `StatisticalAnalysis` callables with a stub returning `{'error': ...}`
  left 23 of 26 tests passing. Each repair is verified by a mutation that reintroduces the
  condition it names, and the two pattern-driven tests additionally fail when their
  pattern stops matching, rather than going quietly blind a second time.
- **Dict-style access on the result dataclasses now fails the way a dict fails.**
  `DirectedResult`, `VFlipResult`, `XFlipResult`, `ZFlipResult` and `AperiodicFitResult`
  each carried a copied `__getitem__`/`get` pair, introduced "so callers written against
  the older dict-returning functions in this module keep working". It did not keep them
  working. `__getitem__` was `return getattr(self, key)`, so a missing key raised
  `AttributeError` and a migrated call site's `except KeyError` did not catch it; and
  with no `__contains__` defined, `"method" in result` fell back to the integer index
  protocol and raised `TypeError: attribute name must be string, not 'int'`. The
  behaviour was only ever tested for keys that were present, which is how five copies of
  a broken promise survived. A miss now raises `KeyError`, a non-string key is a miss
  rather than a `TypeError`, and `in` answers. **Every key that resolved before resolves
  to the same value**; only the behaviour on a key that does not resolve changed.

- **`jrsa` recorded a `batch_size` it never used.** The parameter was accepted,
  documented as "Chunk size for large arrays", and copied into the result's
  `parameters` -- and nothing chunked. `_chunk_tensor`, the module's only chunking
  helper, had no callers: across `batch_size` None, 1, 4, 32 and 10000 the value, p-value
  and interval are identical, and the helper is entered zero times. A result could
  therefore carry `batch_size=32` in its provenance for a run that made one pass. This is
  the defect already fixed here for `device` and `backend`, and the same rule applies --
  `parameters` carries the request, `execution` carries what ran -- so
  `execution['batch_size']` is now recorded, and is always None because jrsa does not
  chunk. The helper is deleted rather than left where it reads as an implementation.
  **No number changes.**
- **`jrsa`'s confidence interval does not follow `alpha`, and now says so.** `alpha`
  sets the significance threshold for the multiple-comparison correction; it never
  reaches `_bootstrap`, which takes a fixed 2.5/97.5 percentile interval. `alpha=0.5`
  and `alpha=0.01` return the same interval. The docstrings for `alpha` and `ci` state
  the fixed 95% level; the interval itself is unchanged, and a test pins it so that
  changing the level has to be deliberate.
- **`classify_layer_from_depth` still called `jnwb.laminar` forthcoming.** It has
  shipped: the module imports and `vflip`, `VFlipResult`, `xflip` and `XFlipResult` are
  all exported. A reader following the cross-reference was told the thing they were being
  sent to did not exist yet. The qualifier is removed and `docs/api.md`, which is
  generated from the docstrings, is regenerated.
- **The import benchmark was timing an import it had slowed down 3.3x, and its receipt
  was five releases stale.** `scripts/benchmark_import.py` started `tracemalloc` before
  its timer, so the import it measured ran with allocation tracing on. Seven interleaved
  fresh-process repetitions: 7724 ms traced against 2317 ms clean. Moving the
  `tracemalloc.start()` below the timed region is not the fix -- the allocations have
  already happened by then and the peak comes back 0.0 MB -- so timing and memory are now
  measured by separate probes in separate processes. The regenerated receipt reports
  2151 ms warm where the old one reported 6244 ms, and 10460 ms cold where it reported
  39342 ms. Nothing gated the receipt, unlike the vFLIP one, so
  `artifacts/benchmarks/import_profile.txt` still announced "jnwb 0.1.6 (111 public
  symbols)" at 0.2.4 with 155, and `import_breakdown.json` was older still at 0.1.5 --
  while itself recording an importtime tree of 1898 ms against its own 6859 ms warm
  median, the same contradiction visible inside one file. The regenerated pair is 2348 ms
  and 2151 ms: two measurement methods that now agree within 9%. `tests/test_import_profile_receipt.py` now fails when
  either receipt names a different version than `jnwb.__version__`, when the timing probe
  instruments the import, and when the probe's own number disagrees with an independent
  wall-clock import. `--write` regenerates both receipts, so the gate is satisfiable by
  the command `AGENTS.md` documents. The superseded `vflip_calibration_0.2.2.md` and
  `vflip_calibration_raw.json`, which described the pre-density-normalized support score
  and carried no estimator hash, are deleted.
- **`docs/install.md` claimed the deferred imports keep `import jnwb` fast.** They do not.
  `import jnwb` takes about 1.9 s, and about 1.8 s of that is `scipy`, `pandas` and `pynwb`,
  which the eagerly imported surface needs. What the deferrals buy is keeping
  `scikit-learn`, `statsmodels`, `matplotlib` and `joblib` out of the import, which nothing
  guarded until now -- the existing extras test only covers packages declared as extras, and
  these are not. `tests/test_import_lazy.py` now pins the eager third-party surface, so a
  newly added eager heavy dependency fails a test instead of reaching a release. The install
  page says what the import costs and where the time goes.
- **`xflip` re-summed the same diagonal slice inside its dynamic-programming loop.**
  `_optimal_contiguous_partition` answered the off-diagonal half of `W(u, v)` from a 2-D
  prefix sum in constant time, then computed the diagonal half as
  `np.sum(np.diag(corr)[u:v])` on every call. `np.diag` returns a view, so nothing was
  copied, but the call, the slice and the reduction together cost 4.82 of the 5.56
  microseconds an `interval_w` call took -- 87% of it -- and the DP makes about 93000 of
  them at 256 channels, once for the observed matrix and once per surrogate. Prefix-
  summing the diagonal once makes `xflip` 3.6x to 3.9x faster on the partition step at
  128 channels and above, and 3.3x end to end at 128 channels with the default 200
  surrogates: 10.63 s to 3.22 s. `block_bounds`, `boundaries`, `labels`, `modularity`
  and every p-value are unchanged. The change is not bit-identical in the DP's internal
  values -- a difference of two running totals rounds differently from a pairwise
  reduction, by up to 4e-15 here -- but those values cannot reach the answer: for a
  fixed `(k, j)` every candidate partition tiles `[0, j)`, so the per-block diagonal
  terms sum to the same constant in every candidate and cancel out of the comparison,
  and the returned modularity is computed separately from the labels.
- **Two CUDA paths were slower than their CPU siblings, one by 23x, because they
  launched one kernel per element.** `UnitAnalyzer._acg_vectorized` had two GPU branches
  and neither was usable at scale: below 30000 spikes it built the full `N x N`
  difference matrix, which at 29999 spikes -- just under the threshold the code treated
  as safe -- asks for 6.71 GiB of device memory for one autocorrelogram; at or above
  30000 it chunked by 1000 and then looped in Python *inside* the chunk, so 35000 spikes
  meant 35001 uploads of a loop-invariant `bin_edges`, 35000 `cupy.histogram` launches
  and 70000 forced device-to-host synchronisations. `_welch_csd_gpu` appended one device
  array per Welch segment, 127 of them for a 16384-sample trace at `nperseg=256`. The
  cost was the launches, not the host/device transfers: at 35000 spikes the launches are
  76% of the accounted time and the transfers 24%. One `_acg_histogram` now serves both
  devices and histograms once per chunk rather than once per spike, with the chunk width
  taken from the widest window actually present; one strided index builds every Welch
  segment at once; and because `harmonic_analysis`, `spectral_tilt` and `band_power` all
  call the Welch helper as `_welch_csd_gpu(trace, trace, ...)` and keep only `pxx`, a
  `y is x` short circuit stops it computing its own second half and discarding it.
  Paired on an RTX A4000, `T_cuda / T_cpu` for the autocorrelogram goes from 23.302 to
  0.060 at 35000 spikes, and the Welch helper from 1.493 to 0.100 at `nperseg=256`.
  Every output is unchanged bit for bit: the autocorrelogram counts match the previous
  implementation on both devices, and 112 of 112 Welch arrays across 28 input cases are
  identical. The three entry points remain slower on CUDA below roughly 22500 samples,
  where the fixed transfer-and-plan cost is most of the call; that crossover is now
  documented in each `device:` parameter rather than papered over by routing on input
  length, which would make the answer depend on trace length. Receipt:
  `artifacts/benchmarks/gpu_launch_overhead_0.2.5.md`.
- **With a GPU present, two `device='cuda'` requests were denied in silence.**
  `jnwb/_backend.py` covered two denial reasons -- no usable device, and a device that
  failed part-way through -- and missed the third: a device that exists but which this
  code path cannot use. `vflip` assigned the resolver's answer to `_` and `laminar.py`
  contains no cupy or torch call anywhere, so the request could never be honoured;
  `fit_var_bivariate` gated its GPU branch on `... == CUDA and ridge <= 0`, after
  resolving. Measured on an RTX A4000 by counting `cupy.asarray`: both reached the GPU
  zero times and warned zero times. The caller *without* a GPU was warned and the caller
  *with* one was not, so the better the hardware the quieter the denial. A new
  `jnwb._backend.warn_no_gpu_path` names that third reason, `rdm`'s existing inline
  warning now goes through it, and every `device='cuda'` call either reaches the GPU or
  says why not. Two further defects found while reproducing: `select_optimal_lag`
  re-resolved the device inside its lag loop, so one call with `max_lag=6` emitted six
  identical warnings (`granger_causality(order='auto')` reaches it up to `2*max_lag + 2`
  times), and every one of those warnings named `fit_var_bivariate`, which is not
  exported. Public entry points now resolve once and announce under their own name;
  `fit_var_bivariate` and `select_optimal_lag` take a `context` argument for it.

- **`device=` changed the numbers `gpu_pca` and `compute_population_trajectory`
  returned.** `AGENTS.md` invariant 6 says the device never changes a number; on a live
  RTX A4000 both broke it. `gpu_pca` cast to float32 inside its CUDA branch while
  `_svd_numpy` stayed in float64, and neither function pinned an SVD sign, so
  `gpu_pca(X(4000, 60), n_components=3)` disagreed across devices by
  `max|cpu - cuda| = 8.005` on the returned projections. Align the signs by hand and the
  residue was 6.5e-04, the float32 part. `compute_population_trajectory` was float64 on
  both devices already -- it uses `torch.as_tensor`, not a cast -- and differed only by
  sign, which showed as `max_rel = 2.0`, a trajectory reflected through the origin.
  The working dtype is now chosen before the device branch, by numpy's own linalg
  promotion rule, so both branches see one array; float16 input consequently works
  instead of being rejected on CPU and silently computed in float32 on CUDA. A new
  `jnwb.gpu_pca.pin_component_signs` forces each component's largest-magnitude loading
  positive -- the `sklearn.utils.extmath.svd_flip` convention -- and both functions apply
  it to whichever branch ran. Measured after: 3.1e-12 and 6.5e-13, with no post-hoc
  alignment. `explained_variance_ratio` is unchanged, being sign-invariant. Component
  signs may now differ from previous releases; the subspace, the variance and everything
  reconstructed from the pair are identical. The CUDA path remains the faster of the two
  in float64 (24.2 ms against 29.8 ms on an A4000).

- **Tutorial 00 broke on the two most common foreign-file shapes.** It is the page for a
  file you know nothing about, and it read `acquisition["rate_hz"]` unguarded while
  iterating `info["acquisitions"]` alone. A file storing `timestamps` instead of a
  constant rate printed `None Hz` and then died at section 4 with an uncaught
  `AcquisitionNotFoundError: Series 'lfp' has no constant sampling rate`. A file whose LFP
  lives in a processing module -- where an `LFP` container usually lives -- printed no
  continuous line at all, silently skipped the alignment, and still claimed "Layout
  discovered and aligned without assuming a schema"; the string `processing_continuous`
  did not appear in the script. It now reads both lists, says in words what each absent
  value means, catches an `NWBInspectError` from a series it cannot read, and closes by
  reporting what actually happened. On a processing-module file it recovers the injected
  23.0 Hz it previously never looked for.

- **`epoch_continuous` turned a non-finite onset into an in-bounds extraction of
  nothing.** `np.round(nan * fs).astype(np.int64)` is `INT64_MIN`, and `idx + n_pre` then
  overflowed to a large *positive* start with a large *negative* end. The bounds test
  `0 <= start and end <= n_samples` is true of that pair, so the window took the
  in-bounds branch and `arr[start:end]` returned an empty slice: one epoch of shape
  `(0,)`, reported as a clean extraction, beside a `time_axis_s` of 800 samples. Mixed
  with one valid onset it reached `np.stack` and raised `ValueError: all input arrays
  must have the same shape` -- a numpy error naming neither the onset nor the argument.
  A non-finite onset now raises `InvalidOnsetValueError` naming its index, which is the
  refusal `events` and `event_onsets` already gave for the same value.
- **Onsets on a different clock from the data returned a confident all-NaN array.**
  `start_time` is seconds in the NWB specification and milliseconds in plenty of the
  toolboxes that write these files. Onsets of 1000-5000 against a 1.0 s recording gave
  `epoch_continuous` shape `(5, 800)`, correct dtype, correct time axis, every value NaN,
  and no warning; the mean is NaN, the spectrum peaks at 0 Hz and the figure is blank.
  Under `boundary_policy="nan"`, a warning is now issued when most epochs fall entirely
  outside `[0, n_samples)`, naming both spans and the likely unit. A single stray event
  does not warn, and an epoch overhanging either edge of the recording is ordinary and
  still silent. `time_unit` on an `EventTable` remains a label: the interval table
  carries no extent to check it against, so the check lives where the onsets meet the
  continuous data.
- **A sampling rate was read from one series and reported beside another's samples.**
  `_find_series_leaf` walked a container's whole subtree with `visititems` and took the
  first `data` leaf and the first `rate` leaf **independently**. On an `LFP` container
  holding `lfp_alpha` at 1000 Hz and `lfp_beta` at 500 Hz, `inspect(path)` reported
  `rate_hz: 500.0` beside `data_path: .../lfp_alpha/data` and `data_shape: [100, 4]` --
  `lfp_beta`'s rate against `lfp_alpha`'s array. `inspect(nwb)` said 1000 Hz and
  `acquisition_channel` returned `lfp_alpha` at 1000 Hz: three answers for one object.
  A rate that belongs to different samples is not a visible error; it shifts every
  frequency by the ratio of the two rates. `data` and `rate` now always come from the
  same group, and a container holding several series yields several members rather than
  one blend of them.
- **`acquisition_channel` returned a transposed recording as a channel trace.** The
  channel axis of a 2-D series was decided by `shape[0] >= shape[1]` -- whichever side is
  longer -- and `acquisition_channel` did not consult even that: it always sliced
  `data[:, channel]` and bounds-checked `shape[1]`. On a channel-major `(64, 1000)`
  `ElectricalSeries` with 64 electrodes, `channel=0` returned the 64 samples `data[:, 0]`
  -- one instant across all channels -- as a 1000 Hz trace; `channel=999` returned
  another such slice instead of raising; and `channel=1000` raised `Channel index 1000
  out of range for series 'es' with 1000 channels` for a file with 64 of them. pynwb
  itself warns on write that such data "is oriented incorrectly", so this is an
  orientation real files are in. The axis is now read from the series' own electrode
  region -- not from the longer side, and not from the whole electrode table, since a
  series may cover a subset of a 384-channel probe -- at all three sites that report
  `layout` and in `acquisition_channel` itself. Where the electrode count settles nothing
  (neither dimension matches it, or the array is square so both do) `layout` is
  `"ambiguous"` and reading a channel raises `AmbiguousLayoutError` rather than return a
  plausible-looking array with the wrong meaning. Time-by-channel files are unaffected,
  and now hold by the electrode count rather than by being taller than wide.
- **jnwb could not read a single-column table that plain pynwb reads.** The smallest
  units table a lab writes has one column, so on disk
  `colnames = array(['spike_times'])`. jnwb's builder repair scalarizes any length-1
  array attribute -- it exists for `description = array(['probe desc'])` -- which turned
  that into the string `'spike_times'`, and the next `list(...)` spelled it out one
  character per column: `ConstructError ... 'colnames': array(['s','p','i','k','e','_',
  't','i','m','e','s','spike_times'])`. Every entry point failed on a file pynwb reads
  without complaint: `inspect`, `events`, `unit_spike_times`, `acquisition_channel`,
  `get_all_units_metadata` and `electrode_inventory`. `colnames` is specified as a
  sequence, so it is excluded from the scalarization, and the `list(...)` is guarded as
  well. This affects **any** single-column `DynamicTable`, not only `units` -- a
  one-column table in a processing module failed identically, and the units-specific
  guard could not have saved it.
- **`decoding` refused valid label sets and reported a false status for others.**
  `np.bincount(labels.astype(int))` counts every integer below the maximum as a class,
  including absent ones, and refuses anything that is not a contiguous non-negative
  integer. One separable 40-trial dataset, 20 per class, relabelled: `{0, 1}` gave
  accuracy 0.846; `{1, 2}` and `{0, 2}` gave `status="insufficient_trials_for_cv"` with
  every metric NaN; `{-1, 1}` raised `'list' argument must have no negative elements`;
  `{'a', 'b'}` raised `invalid literal for int()`. `nested_cv_linear_svm`,
  `majority_baseline` and `fold_majority_baseline` now count with `np.unique`, so any
  two-class label set of adequate size decodes and every metric is identical across
  relabellings. A new `status="insufficient_classes_for_cv"` covers a single-class input,
  which is not a claim about trial counts. Contiguous 0-based integer labels produce
  byte-identical results.
- **`f1` and `auc` depended on what the classes were called.** Both were left to
  scikit-learn's `pos_label=1` default, so `{0, 1}` scored f1 = 0.857143 and the same
  trials as `{1, 2}` scored 0.842105. `{0, 2}` and `{'a', 'b'}` raised
  `pos_label=1 is not a valid label`, and a bare `except ValueError` turned that into a
  NaN AUC for a computable value. The positive class is now `classes[1]`, the second in
  sorted order, which is the class `decision_function` scores toward.
- **The two-step partition pipeline could not consume its own output.**
  `assign_outer_folds` accepts string group ids and reports `outer_fold_status="valid"`;
  `build_inner_validation_partitions` then raised
  `invalid literal for int() with base 10: 'c2'` on that frame. Group ids are opaque
  labels and are no longer cast to `int`. Fold indices and trial ids, which are genuinely
  positional, still are.
- **`Dataset` could not be used as the dict key its own docstring advertises.** The
  dataclass-generated `__eq__` compared the field tuples, which evaluates
  `units_a == units_b` to a DataFrame and then takes its truth value, raising
  `ValueError: The truth value of a DataFrame is ambiguous`. A dict consults `__eq__` on
  every hash collision -- including between a key and an equal copy of it -- so
  `d[dataset] = x` raised for the one use the custom `__hash__` exists to enable.
  `Dataset` and `EpochCollection` now compare their DataFrame fields with
  `DataFrame.equals`. Equality stays finer than `Dataset.__hash__`, which is the
  direction the hash/eq contract requires.
- **`Result` claimed to be serializable without qualification.** `statistics` is
  `Dict[str, Any]` and in this package normally holds NumPy values, for which
  `json.dumps(result.to_dict())` raises `TypeError: Object of type ndarray is not JSON
  serializable`. The contract now states the condition and the `default=` escape hatch.
  `to_dict()` still converts nothing, so no value is coerced or rounded on export.
- **`ontology` documented an immutability it does not have.** `frozen=True` prevents
  rebinding an attribute, not mutation of the list, dict or DataFrame it points at:
  `dataset.sessions.append(...)` succeeds. The module docstring now says so. The unused
  `hashlib`, `json`, `numpy`, `pathlib.Path` and `logging` imports, which advertised
  content-hashing and serialization the module never implemented, are removed.
- **`python -m jnwb.mcp_server` did not start the MCP server.** The launch command in
  `docs/10_extending_jnwb_and_verification.md` failed with "'jnwb.mcp_server' is a package and
  cannot be directly executed", including against the published wheel with the `mcp` extra
  installed, because the `if __name__ == "__main__"` guard sat in `__init__.py`, which a package
  never satisfies. A `__main__.py` now runs the server and the unreachable guard is gone. The
  entrypoint test previously asserted only that a FastMCP object exists; it now runs the
  documented command.
- **`events` nulled an absent code column in silence.** On a file whose interval table has no
  `codes` column -- the usual case for a file from another lab -- `jnwb.events(path)` returned
  `code_column=None, codes=()` with no warning, and `jnwb.events(path, code_column="condition")`
  for a column that does not exist returned the same thing rather than failing, while
  `event_onsets` with that argument raised. The two now agree: a column named by the caller must
  exist, and the default name being absent warns and names the columns that do.
- **Documentation for getting a file in, rather than only for analysing one.** `docs/agents.md`
  states what `pip install jnwb` does and does not deliver to an agent, documents the three MCP
  tools with a client configuration, and lists the nine skills.
  `examples/tutorials/00_your_own_file.py` discovers a layout instead of asserting a fixture's
  values. Common mistakes gains section 9 on assuming a schema. README and quickstart show
  `code_column=`. The sdist now ships `skills/` and `AGENTS.md`.

## [0.2.4] - 2026-09-16

### Added

- Weighted Phase Lag Index (`wpli`, returning a dict) in `jnwb.spectral`:
  Phase-synchronization metric evaluating segment-resolved imaginary cross-spectra, reducing sensitivity to zero-phase-lag coupling without claiming volume-conduction immunity; reports both standard and debiased squared wPLI.
- Laminar phase gradient analysis (`zflip`, `ZFlipResult`) in `jnwb.laminar`:
  Cross-channel phase-gradient analysis and apparent velocity estimation with phase-frequency linearity verification ($R^2 \ge \text{min\_linearity\_r2}$) and per-channel Fourier phase-randomised surrogate testing.
- Standalone representational dissimilarity matrices (`rdm`, `rdm_similarity`) in `jnwb.rsa`:
  Generates condensed or square symmetric RDMs across conditions or time points with any `scipy.spatial.distance.pdist` metric (e.g. correlation, cosine, euclidean, cityblock); evaluates inter-RDM similarity via rank or linear correlation.
- Comprehensive 8-part synthetic NWB tutorial suite:
  Completely independent, zero-relative-import executable tutorials covering NWB inspection, addressing/metadata, spiking PSTH/latency, continuous LFP/Welch PSD/TFR/wPLI, dual exploratory and permutation statistics, laminar CSD/vFLIP/zFLIP, population ensembles/JRSA/decoding, and end-to-end composite pipelines.

### Changed

- Renamed and unified tutorial structure to match canonical 8-part progression.
- Updated Gate 13 preflight assertions to guarantee exact snippet synchronization for all 8 tutorials.

### Fixed

- **`vflip` located the crossover near the centre of the sampled contacts rather than
  where the motif reverses.** Power was z-scored per frequency across contacts, which
  forces every column to zero mean, so both band depth profiles carried zero spatial mean
  and their difference summed to zero identically. The zero crossing of a zero-sum profile
  sits near the centre of the array whatever the truth is, and for a profile linear in
  contact index it is pinned to the midpoint exactly. On a known motif at SNR 100, true
  crossovers of 5.5 / 7.5 / 11.5 / 15.5 / 18.5 contacts were returned with bias
  +3.98 / +2.17 / -0.01 / -1.92 / -4.75, a slope of about 0.31 estimated contacts per true
  contact; the shift matched the removed spatial mean to within 0.5 contacts. The reported
  crossover therefore depended on where the probe sat relative to the motif, which is the
  quantity being measured. The defect was invisible to the previous calibration, which
  placed every synthetic crossover at the shaft midpoint -- the one location where the bias
  vanishes -- and to `test_known_crossover_recovery_multiple_depths`, whose compact
  symmetric bumps also have zero spatial mean.

  Power is now expressed as min-max relative power per frequency across contacts, and each
  band depth profile is rescaled to [0, 1] before the two are differenced to locate the
  crossover. The relative power fraction `P(c, f) / sum_k P(k, f)` was implemented and
  measured first: being simplex-constrained it fixes each column's sum, so the difference
  again sums to zero and the bias is unchanged (+3.81 / +2.25 / +0.11 / -1.79 / -4.43).
  Any normalization constraining a column's mean or sum carries the defect. Shaft-wide
  median |c* - c_true| at SNR 100 falls from 2.28 to 0.99 contacts, and the old estimator's
  residual does not fall with SNR because it is bias rather than noise.
- **`vflip`'s support score had a frequency-grid-dependent null**, so a fixed threshold
  meant different false-positive rates at different recording lengths and `nperseg`. Under
  the null a Euclidean norm over the whole grid grows as `sqrt(n_freqs)` while a band mean
  over `n` bins has null scale `1/sqrt(n)`; the score combined one of the former with two of
  the latter, giving a null that fell as `n_freqs^(-1/2)` and a null median that shifted by
  `-0.5 * ln(n_freqs)`. That law reproduced the measured shift across a 126 -> 1001 bin
  sweep to within 0.27, exactly at the largest grid. The spectral distance is now an RMS
  across bins and the band-derived terms are returned to unit null scale, so every factor is
  grid-free. The calibration now measures a null false-positive rate varying by 0.000 and a
  recovery rate of 1.000 across the (length, nperseg) sweep.
- **`vflip`'s acceptance was not false-positive controlled.** At the old default threshold
  of 6.0 the estimator accepted white noise in 0.37 of trials, AR background in 0.43 and
  parallel bands in 0.30, against 0.47 recovery for a true motif at SNR 1 -- a rank AUC of
  0.568, with no threshold separating the two distributions. The estimator is recalibrated
  end to end by `scripts/calibrate_vflip.py` over crossover location, channel count, pitch,
  frequency-grid density, orientation, missing contacts and SNR, against the existing null
  families. AUC is now 1.000 over 120 null and 810 recoverable-alternative trials. The
  default `min_support_score` changes from 6.0 to **3.75**, selected at maximum margin
  inside the band of thresholds satisfying a criterion declared before the calibration ran:
  pooled null false-positive rate <= 0.05, recovery >= 0.80, median |c* - c_true| <= 1.5
  contacts among accepted trials in the central half of the shaft, and null false-positive
  rate varying by <= 0.05 across frequency grids. At 3.75 the measured values are FPR 0.000,
  TPR 0.999, median error 1.41 contacts and grid spread 0.000. Threshold 6.0 was not
  preserved for compatibility: it belonged to a different score.

  Recovery requires a clearly resolved motif: acceptance is 0.000 at SNR <= 2, 0.367 at
  SNR 5 and 1.000 from SNR 10, and median crossover error falls from 1.59 contacts at SNR 10
  to 0.95 at SNR 50. At 5000 samples neither the old nor the repaired estimator localizes
  the crossover to better than about 6 contacts at SNR 4, which is an information limit of
  the recording rather than a property of the normalization.

- **`vflip`'s crossover is still shrunk toward the centre of the shaft, and the receipt now says
  so.** The 0.2.3 defect was a zero-sum profile that pinned the crossing to the centre
  regardless of SNR. What remains is attenuation that recedes as noise falls. Regressing
  estimate on truth over crossovers at 20-80% of a 24-contact shaft, now computed by the
  calibration itself: slope 0.703 at SNR 20, 0.804 at SNR 100, 0.864 at SNR 1000, against 1.0
  for an unbiased locator. At SNR 20 the mean signed error runs from +2.40 contacts at 20% of
  the shaft to -1.87 at 80%. The previous receipt could not have shown this: its crossover table
  reported only median |c* - c_true|, which stayed between 1.04 and 1.81 at every depth because
  it cannot see a bias that changes sign. Cause: at SNR 20, 35 of 51 gamma-band bins and 7 of 12
  beta-band bins carry no laminar source, so the per-trial min-max range is estimated from noisy
  extremes and each profile is compressed toward its interior. No correction factor is applied;
  the shrinkage is reported in the calibration, documented on `VFlipResult.crossover_contact`,
  and pinned by a test in both directions. Treat a crossover near either end of the shaft as a
  bound, not a point estimate.
- **`phase_locking_index` folded the recording onto itself.** It called `np.interp(spike_times,
  lfp_timestamps, lfp_phase, period=2*np.pi)`, but `np.interp`'s `period` is the period of the x
  coordinates, not of `fp`, so spike times and LFP timestamps were wrapped modulo 6.2832 SECONDS
  and each spike took the phase of an unrelated moment. A unit locked to phase 0 with 2 ms
  jitter, true resultant length 0.995, reported `pli` 0.80 over 6 s, 0.31 over 60 s and 0.10
  over 600 s. Phase is now interpolated through its unit vector, giving 0.804 / 0.808 / 0.803
  and a `rayleigh_z` of 473.9 against an analytic 474.0. The Rayleigh p-value is also clamped
  below: the series expansion goes negative at large z, and a negative p passes every `p <
  alpha` test.
- **`compute_response_metrics` differenced raw spike counts over unequal windows.** The defaults
  are 0.200 s of baseline against 0.150 s of response, so a unit firing at a constant rate
  scored a response it did not have, growing as the square root of the rate: z = -0.47 at 20 Hz,
  -1.04 at 100 Hz, -1.91 at 500 Hz. `classify_response_significance` takes abs(z), so a fast
  enough non-responsive unit is certified as responding. Rates are now z-scored instead of
  counts, which is exactly a no-op when the windows are equal. A baseline with no across-trial
  variance also left `response_zscore` at its initialised 0.0, reading as no response for the
  strongest possible evidence -- a unit driven at 133 Hz from a silent baseline returned z =
  +0.00, confidence none. It now returns NaN with confidence undefined.
- **`jrsa` permuted the feature axis for whole-representation metrics.** `cka`, `rv`, `hsic`,
  `distance_correlation`, `procrustes` and `rsa` reshape to (n_observations, n_features) and
  ignore `axis`, and all are invariant to a permutation of features, so the null collapsed to a
  point mass and p was exactly 1.0 whatever the data said. The permutation axis is now taken
  from the metric. Measured false-positive rate over 200 independent datasets: 0.060, 0.045,
  0.055, 0.050, 0.050 and 0.050 against a nominal 0.05, with a linearly related pair still
  detected at p <= 0.006.
- **`_adf_pvalue` compared a Dickey-Fuller t-statistic to the normal distribution.** The DF null
  is shifted well to the left (5% critical value near -2.86 with a constant, not -1.645), so it
  certified 48.4% of pure random walks as stationary at n = 200 and 46.0% at n = 2000, while its
  docstring called itself conservative. `stationarity_ok` and `ok_for_interpretation` on Granger
  results were therefore near coin flips on exactly the series a user needs warned about. It now
  defers to `statsmodels` MacKinnon p-values for the same regression: 0.049 at n = 200 and 0.049
  at n = 2000, with 100/100 stationary AR(1) series still rejecting the unit root.
- **`cross_modal_comparison` reported the selected lag's uncorrected p-value.** On independent
  white noise over 101 lags it called 99.5% of runs significant. It also built its lag set as a
  symmetric sweep of +-min(|lo|, |hi|), so (0, 500) searched nothing and (100, 500) searched
  +-100 ms. The lag set is now exactly what was documented, and the result carries
  `lag_corrected_pvalue` from a circular-shift max-statistic null (measured FPR 0.043). Because
  a shift relands a peak inside the window about n_lags / n_samples of the time,
  `lag_search_resolution_floor` reports that ratio and `warnings` flags it above 0.05.
- **`transfer_entropy` was blind to a collapsed discretization.** A collapse yields FEWER joint
  states, so `samples_per_joint_state` rises and the undersampling check stays quiet. With spike
  counts averaging 0.05-0.1 per bin, every quantile edge lands on 0 and the series maps to one
  symbol: on data where X drives Y at lag 1 it returned TE = 0.0000 bits, p = 1.0,
  `ok_for_interpretation` True and no warnings. It now reports `n_realized_states_x` and
  `n_realized_states_y`, and warns when the discretization collapses.
- **`permute_labels` with `scheme=within_group` returned a vacuous null for nested designs.**
  When each group carries one condition there is nothing to permute: 1000 of 1000 draws came
  back identical, and `build_permutation_plan` emitted a 500-row manifest carrying one distinct
  digest while reporting `group_composition_preserved: True`. It now raises with the reason and
  the alternatives, and the plan reports `n_permutable_groups` and `n_distinct_draws`.
- **`repair_lfp_trials` substituted away time-locked evoked responses.** The detector is cross-
  channel synchrony, and an evoked response is synchronous by construction, so it was flagged
  like an artifact and replaced by the cross-trial median of itself. The trial average survived
  while single-trial variability did not: the correlation between true single-trial amplitude
  and the repaired peak fell from 0.9996 to 0.4607. A new `max_trial_fraction` (default 0.5)
  never substitutes a sample flagged on more than half the trials, which is where the
  substitution becomes self-defeating. A rare artifact on 3 of 40 trials is still fully
  repaired.
- **`_rv` was not centred, although `_cka` beside it is.** Any two representations sharing an
  offset therefore looked identical: two independent Gaussian samples shifted by +50 returned RV
  = 1.0000, now 0.178.
- **`xflip` treated a skipped surrogate test as a passed one.** With `n_surrogates=0` it set
  significance True and returned `accepted=True` alongside p = NaN. Pure noise was accepted in
  119 of 120 seeds, and the test would have rejected 113 of them. Acceptance now requires the
  test to run, matching `zflip`'s documented contract.
- **The top multitaper bin was half-size at odd `n_fft`.** One-sided scaling excluded the last
  bin unconditionally, but an rfft grid only has a Nyquist bin when `n_fft` is even. Integrated
  power against the variance went from 0.9111 to 0.9999 at n = 101.
- **`imaginary_coherency`'s denominator guard was unit-dependent.** The product of two PSDs
  scales as the fourth power of amplitude, so an absolute 1e-30 clip collapsed the estimate for
  recordings stored in smaller units: `icoh_mean` held at -0.5144 to a scale of 1e-6, then fell
  to -0.000142 at 1e-8 and to zero below. The floor is now relative, and the estimate is
  identical across sixty decades of amplitude.
- **`confirmatory_compare` told callers to re-correct `q_parametric` across hypotheses,** which
  compounds two BH passes. It now points at the raw p-values. `jrsa` reports a shape mismatch as
  a contract error naming both shapes rather than a raw broadcast failure, and the release
  gate's own smoke test is repaired: it asserted `hasattr(wpli_res, 'wpli')` on a dict, which is
  always False, and used a key name, `wpli_debiased`, that does not exist.
- **`jrsa` accepted a seed it never used.** It spells its seed `random_state`, while
  `connectivity`, `laminar`, `statistics` and `permutation` all spell it `seed`; and it forwards
  unrecognised keywords to the metric, every one of which ends in `**kwargs`. `jrsa(...,
  seed=0)` was therefore accepted in silence with `random_state` still None, so the permutation
  test was entropy-seeded and the result was not reproducible: four identical calls on one
  dataset returned p = 0.2736, 0.3333, 0.2637, 0.2935, against 0.2189 four times with
  `random_state=0`. The same hole swallowed misspelled and misdirected metric options, which
  then returned a default-parameter answer. `seed` is now an alias for `random_state`, passing
  both is refused, and a keyword the chosen metric does not declare raises a TypeError naming
  the options it does accept.
- Strengthened scientific boundary assertions: replaced all absolute volume-conduction immunity claims with precise zero-phase-lag sensitivity reduction statements.
- Upgraded release gate smoke suite to test 0.2.4 additions (`wpli`, `zflip`, `rdm`).
- Gate 6 (dataset independence) now scans every durable user-facing surface recursively:
  `docs/**/*.md`, `examples/**/*.py`, `examples/**/*.ipynb`, and root documents (`README.md`,
  `CONTRIBUTING.md`, `AGENTS.md`, `CLAUDE.md`). Previously `README.md`, `CONTRIBUTING.md`,
  `examples/quickstart_jnwb.py`, `examples/notebooks/*.ipynb`, and non-numbered example modules
  were unscanned. `CHANGELOG.md` remains exempt as a historical record, now via a named
  `DATASET_SCAN_EXEMPT` entry carrying its reason rather than a silent omission.
- Corrected the Gate 6 docstring, which described a narrower surface (`docs/*.md`,
  non-recursive, `examples/` unmentioned) than the code actually scanned. An independent RC
  audit read the docstring rather than the globs and reported a coverage gap that did not exist;
  a regression test now asserts the docstring names the surfaces it scans.
- Release gate STEP 0 checks that the required release/test tooling declared by the `[test,docs]`
  extras is present in the active environment before qualification begins, exiting with the exact
  provisioning command when it is not. This is a presence check on the named distributions, not a
  proof that every dependency constraint is satisfied; `pip check` in STEP 6 remains the
  authoritative installed-distribution consistency check. Motivation: an interpreter lacking the
  declared docs tooling does not fail loudly, it silently measures something else -- an audit run
  on such an interpreter recorded `1 failed, 1021 passed` where the strict-MkDocs test could not
  import MkDocs.
- README no longer presents `pip install jnwb==0.2.4rc1` as currently available. The unpublished
  release candidate is labelled as such, with the executable source-install path given and the
  post-publication command retained (preserving version synchronisation for Gate 10).
- Removed the one-off `jnwb-unified-rev.md` external-review dossier from the repository root.
- **Canonical tutorial NWB built an out-of-bounds electrode region.**
  `build_canonical_tutorial_nwb` assigned its two units to the hardcoded electrode rows `[10]`
  and `[18]`, valid only while `n_channels > 18`. At `n_channels=12` the second unit referenced a
  nonexistent row: newer HDMF rejects the dangling `DynamicTableRegion` at write time, while
  older HDMF accepted it and raised only on read, so CI failed on every matrix leg while stale
  local environments passed. Unit contacts are now derived from `TUTORIAL_UNIT_DEPTH_FRACTIONS`
  (a unit sits at a physical depth on the shaft, so its row scales with the contact count),
  reproducing the historical `(10, 18)` exactly at the default 24 channels and staying in range
  for any supported length. `_validate_electrode_indices` enforces
  `0 <= index < len(electrodes)` at construction with the offending values named, on every
  dependency version, and the chosen contacts are reported in the ground-truth dictionary.
  Nothing is truncated, padded, duplicated, or invented: an unrepresentable request raises.
- The tutorial laminar crossover contact is now an explicit constant with a guard.
  `crossover_true` was hardcoded at 10.5 while `synth_laminar_motif` requires
  `c_crossover <= n_channels - 1`, so any `n_channels <= 10` failed deep inside the motif
  generator with a message about `c_crossover` rather than about the caller's argument.
  `build_canonical_tutorial_nwb` now rejects such a shaft up front, naming the constraint. The
  crossover is ground truth the tutorials assert against, so it is not scaled to fit.
- **CRITICAL: cross-spectral ratio estimators reported perfect coupling for independent
  signals.** `cross_area_coherence` used `nperseg = min(N, 4096)`, which puts every input up
  to ~8192 samples into a *single* Welch segment. With one segment
  `|X Y*|^2 = |X|^2 |Y|^2` holds exactly, so magnitude-squared coherence is 1.0 at every
  frequency for any two signals. Two independent Gaussian traces of 4096 samples -- about 4 s
  of LFP at 1 kHz -- returned `band_coherence = 1.0` with no warning, and the surrogate test
  could not catch it because the surrogates saturate at 1.0 as well. This is an algebraic
  non-identifiability, not an estimation error.
  The same defect was then found in two sibling estimators that divide a cross-spectrum by the
  auto-spectra: `imaginary_coherency` (`coh_mag_mean = 1.0` for N <= 1024) and `wpli`
  (`wpli = 1.0` for N <= 256 under its default `nperseg = min(N, 256)`).
  All three now derive `nperseg` as `N // 8` (capped at each function's previous ceiling) and
  refuse any segmentation yielding fewer than `MIN_IDENTIFIABLE_SEGMENTS = 2` segments. Two is
  the mathematical boundary, not a quality recommendation: the null expectation of coherence
  is still about `1/K`, so K = 2 carries a null mean near 0.5. The new default was chosen by
  comparing candidate segment lengths on independent and known-coupled synthetic signals for N
  from 1024 to 60000; `N // 8` separated coupled from null better than `N // 4` at every length
  tested, and no fixed length serves both short and long traces. Null coherence was measured
  rather than assumed: `E[C]` tracks `1/K` to within 1-6 %, the excess growing with K because
  50 %-overlapped segments are correlated. `wpli_debiased_sq` was verified to remain
  approximately unbiased under the null (|mean| < 0.02 across K), which plain wPLI is not.
  `cross_area_coherence` gains `nperseg` and `noverlap` parameters and reports `nperseg`,
  `noverlap` and `n_segments_used`, since K is required to interpret any coherence it returns.
  Surrogates are verified to use the same segmentation as the observed statistic.
  Plain PSD estimators are deliberately NOT gated: a one-segment periodogram is noisy but not
  degenerate.
- `zflip` shared the single-segment degeneracy, and it disabled one of zflip's own gates.
  Its default `nperseg = min(N, 256)` gave one STFT segment at `N <= 256`, where adjacent
  wPLI saturates at exactly 1.0 for any input -- so the documented `min_wpli` acceptance
  gate passed unconditionally, and a gate that always passes is not a gate. The default is
  now `min(max(N // 2, 8), 256)` and a segmentation yielding fewer than two segments is
  refused. `N // 2` rather than the coherence family's `N // 8`: zflip fits a phase slope
  inside a narrow band and needs at least 3 frequency bins there, so segment length cannot
  be traded for segment count. This preserves the historical 256-sample segment for every
  `N >= 512`, and a real travelling wave is now detected at `N = 256`, where the saturated
  statistic previously caused rejection.
- Corrected the `zflip` docstring claim that the delay bound `|tau| < 1 / (2 df)` prevents
  phase-wrap aliasing. The bound is applied to the *estimated* delay, and a true delay
  beyond the interval aliases to a smaller value that satisfies it, so the check cannot by
  itself detect wrapping. The surrogate test is what rejects such cases, so `accepted`
  rather than `delay_identifiable` is the field to trust for large true delays.
- **INTENTIONAL BREAK (0.2.4):** `wpli` and `imaginary_coherency` raise `ValueError` for
  traces of unequal length. Both took `n = min(len(x), len(y))` and silently discarded the
  tail of the longer trace, so the two signals no longer described the same interval and
  nothing in the result said so. Truncation changes which samples are compared, which is the
  caller's decision. Found during the 0.2.4-04 independent numerical audit.
- Corrected stale `nperseg` defaults in the `wpli` and `imaginary_coherency` docstrings, which
  the segmentation repair had invalidated. A test now asserts the documented default matches
  the implementation, since this drift was introduced by a repair and not caught by any gate.
- **INTENTIONAL BREAK (0.2.4):** `cross_area_coherence` raises `ValueError` when its two
  traces have different lengths. It previously logged a warning and returned a dict of zeros:
  `peak_coherence_value` was `0.0`, which is exactly what a genuine measurement of no coupling
  looks like, no key marked the result as absent, and the log line is invisible unless the
  caller configured logging. Coherence is defined only between paired samples, so unequal
  lengths are malformed input rather than a zero-coupling result; truncating or padding to a
  common length is the caller's decision. The pre-release candidate is the correct boundary for
  removing this behaviour.
- `cross_area_coherence` rejects 2-D input with a `ValueError` naming the argument and its
  shape. A 2-D array was previously indexed as if it were 1-D, making `nperseg` the channel
  count and taking `argmax` over the flattened array; every shape tested failed, but with an
  `IndexError` or `TypeError` from inside the estimator that named neither the argument nor
  the contract.
- Release verification now exercises the tutorials against the **installed wheel** (0.2.4-03).
  The distribution job previously imported the installed package and ran four inline workflows;
  the tutorials -- the only end-to-end consumers of the public API -- ran solely from the
  checkout with the repository on `PYTHONPATH`. That configuration cannot detect a subpackage
  omitted from the wheel or an import that only resolves from the source tree. CI and the local
  release gate (new STEP 8) now run all eight tutorials on the clean-venv interpreter with
  `PYTHONPATH` stripped and the working directory outside the repository, and
  `tests/test_workflow_release_policy.py` fails if either check is removed or reordered before
  installation.
- The release gate no longer hardcodes the expected version. `jnwb_source_version()` parses
  `__version__` from the source tree and the isolated smoke test compares the installed wheel
  against it, removing a hand-maintained literal of the same drift class the documentation
  gates exist to prevent.
- **wPLI and zFLIP depended on the amplitude units of the input.** An absolute `1e-12`
  cutoff on the imaginary cross-spectrum was applied after STFT scaling. For a coupled pair at
  amplitude `1e-6`, `wpli` returned `0.0`; at `1e-4` to `1e-3`, the range of volt-scaled LFP,
  `wpli_debiased_sq` returned `0.0`; and `zflip` rejected a real travelling wave at `1e-6`.
  The cutoff is now relative to each cross-spectral magnitude (`spectral.ZERO_LAG_RTOL`), and
  `wpli`'s CPU path, its CuPy path and both `zflip` loops share one implementation. Results are
  identical from amplitude `1e-9` to `1e3`.
- **INTENTIONAL BREAK (0.2.4):** `wpli` and `imaginary_coherency` raise `ValueError` for empty
  input, NaN or Inf samples, or a `freq_range` containing no frequency bin. Each previously
  returned `0.0`, indistinguishable from "no coupling". Identical signals still report `0.0`,
  where every imaginary term is exactly zero.
- **`wpli(device='cuda')` never ran on a GPU.** `cupy.divide` rejects `where=`; the error was
  caught and logged, and CPU results were returned. It now executes on CUDA and matches the CPU
  to 1e-15. `wpli` and `imaginary_coherency` resolve the device through `_backend`, reject
  unrecognised device names, and emit a `RuntimeWarning` on fallback instead of a log message.
  See `artifacts/benchmarks/cuda_parity_0.2.4.md`.
- **INTENTIONAL BREAK (0.2.4): `zflip` inference and identifiability.**
  - A delay is identifiable only when every adjacent contact pair is, as the docstring stated.
    The code required about half, and summed every pair's delay into the spatial fit: one
    incoherent contact biased a 12-contact estimate by 16%, and on 3 contacts a delay of
    -9.0 ms was accepted for a true +1.0 ms.
  - `n_surrogates=0` skips the test and now gives `accepted=False`. It previously accepted
    with `p_value=NaN`.
  - `ValueError` for `alpha` outside (0, 1), a negative or non-integer `n_surrogates`,
    `min_linearity_r2` or `min_wpli` outside [0, 1], a malformed `freq_range`, or non-finite
    input. NaN input was previously processed.
  - A result rejected for too few frequency bins reports `mean_wpli` and `adjacent_wpli` as
    NaN rather than `0.0`.
  - Default `nperseg` is `min(max(N // 2, 8), 256)`, unchanged for `N >= 512`; a segmentation
    giving one segment raises. With one segment adjacent wPLI is 1.0 for any input, which made
    `min_wpli` inert for `N <= 256`.
  - The docstring states what the delay measures: the slope of the averaged cross-spectral
    phase, a group delay, which zero-lag mixing pulls toward 0 (equal-power mixing halves it).
    Both statements are tested against constructed signals.
- **INTENTIONAL BREAK (0.2.4): `rdm` and `rdm_similarity`.**
  - `rdm` raises `ValueError` when the metric is undefined for a condition pair (correlation
    distance of a zero-variance row, cosine distance of a zero-norm row). Such distances were
    set to `0`, declaring the condition identical to every other.
  - `jrsa(metric="rsa")` returns NaN in that case again. Delegating to `rdm` in 0.2.4rc1 had
    made it return a finite similarity, where its earlier `pdist` + `spearmanr` implementation
    returned NaN; `tests/test_rsa_oracle.py` compares against that implementation.
  - `rdm_similarity` raises for a non-symmetric matrix, a nonzero diagonal, or a condensed
    length that is not `N(N-1)/2` (including empty input, which returned `0.0`). A zero RDM
    under `'cosine'` returns NaN rather than `0.0`. The docstring notes that its p-value treats
    RDM cells as independent and is not a test of RDM relatedness.
  - `rdm(device=...)` validates the name and warns that there is no GPU implementation; any
    string was previously accepted and ignored. `'manhattan'` is no longer listed as a metric
    (`pdist` does not accept it; use `'cityblock'`).
- **vFLIP calibration receipt described an earlier estimator.** The 0.2.2 receipt predates the
  support-score density normalization and the crossover polarity rule, and no generator was
  kept. `scripts/calibrate_vflip.py` regenerates `artifacts/benchmarks/vflip_calibration_0.2.4.md`
  from the shipped estimator, recording a hash of the `vflip` source that
  `tests/test_vflip_calibration_receipt.py` checks.
- The harness test for hardcoded symbol counts had matched nothing since it was written: the
  `\b` word boundaries in its pattern were stored as backspace characters. Two docstrings in
  `jnwb/rsa.py` had the same corruption (`\rho`, `\tau`, `\frac`).
- **INTENTIONAL BREAK (0.2.4): undefined results no longer come back as numbers.**
  - `spectral_tilt`, `harmonic_analysis` and `band_power` raise `ValueError` for empty, NaN or
    Inf input; they returned 0.0 or NaN powers. A trace with no positive power in range gives
    NaN `exponent`, `offset` and `fit_quality`, and NaN `fundamental_freq` and `harmonic_ratio`,
    instead of 0.0; a constant trace had reported a fundamental at the first bin. All three
    resolve `device` through `_backend`, reject unrecognised names and warn on fallback.
  - `band_power` raises when the baseline has no power in `freq_range`; it returned the linear
    power in place of a dB value. The baseline gets its own Welch grid; a baseline shorter
    than 4096 samples and of a different length from the trace raised `IndexError`.
  - `harmonic_ratio` is P(fundamental) / (P(fundamental) + sum of P(orders 2..N)). Order 1 is
    the fundamental itself and was summed into the harmonics, capping the ratio at 0.5.
  - `laplacian_reference` raises for a single channel, which returned zeros.
  - `rate_in_window` and `fires_in_window` raise for a window of non-positive width (0 Hz and
    `False`), non-finite bounds or spike times, and unsorted spike times, which were miscounted.
  - `shuffle_pvalue_paired` and `shuffle_pvalue_unpaired` raise for NaN or Inf values, which gave
    the minimum p-value 1/(n_shuffles+1), and for `n_shuffles` < 1. The paired test raises for
    unequal lengths instead of truncating to the shorter. Fewer than two observations return
    `(nan, nan)` instead of `(0.0, 1.0)`.
  - `raster_psth` returns NaN mean and SEM for zero onsets (zeros) and validates `win_ms` and
    `bin_ms`.
  - `network_topology` raises for a non-square matrix or a NaN or Inf off-diagonal entry, which
    counted as no edge.
  - `xflip` rejects input containing a zero-variance channel and reports its correlations as NaN.
    They were set to 0, which the partition search reads as a block boundary.
- **Results depended on the amplitude units of the input** (absolute `1e-12` offsets and cutoffs).
  - `jrsa` with `metric` `cka`, `rv`, `distance_correlation` or `cosine`: CKA of the same data was
    0.72, 0.08 at `1e-3` scale and 1e-13 at `1e-6`. These metrics are now scale invariant and
    NaN for a constant or zero input (previously 0.0). `standardize` and `normalize`
    preprocessing no longer add an offset.
  - `vflip` and `vflip_from_lfp`: a motif accepted at unit scale was rejected at `1e-6`, the scale
    of LFP in volts. The PSD is rescaled to its maximum before the per-frequency
    standardization floor. Regenerating `artifacts/benchmarks/vflip_calibration_0.2.4.md`
    reproduced every calibration outcome exactly; only the estimator hash changed.
  - `detect_band_outliers`, and so `repair_band_artifacts`, flagged nothing at `1e-12` power scale;
    the degenerate-scale test is now relative to the data, and non-2-D or non-finite input
    raises. The robust z-scores of `bad_trials_single_channel` and
    `bad_channels_from_correlation` use the same relative test.
- **`jrsa` on CUDA did not match the CPU.** `pearson` returned 0.0 for a constant vector (CPU: NaN)
  and -0.007 for a true -0.27 at `1e-7` scale; `spearman` broke ties by position (-0.072 against
  -0.088 on tied data). The GPU paths now compute the CPU definitions.

## [0.1.8] - 2026-09-11

### Added

- Synthetic structurally representative NWB test fixtures (`jnwb.testing.nwb_fixtures`):
  Deterministic multi-channel ecephys generators supporting co-resident task and mapping
  interval tables, non-code interval columns, custom electrode locations, and processing-module
  packaging styles (`processing_lfp_options()`, `task_only_options()`, `dual_probe_options()`).
- `jnwb.inspect`: Non-destructive inspection of acquisitions, electrodes, units, interval tables,
  and processing-module continuous series with column sample inspection, without guessing default
  event tables.
- Canonical events and onsets workflow: `jnwb.events` and `jnwb.event_onsets` providing explicit
  table selection, non-code interval table extraction, code-based filtering, and seconds/samples conversion.
- Processing-module continuous series discovery: Automatic resolution of LFP series located in
  processing modules (e.g. `processing/ecephys/LFP`) across `inspect`, `resolve_acquisition`, and
  `acquisition_channel`.
- `epoch_continuous`: Generic continuous event epoching primitive with explicit time-to-sample mapping
  via IEEE 754 round-half-to-even (banker's rounding), window bounds (`win_s`), onset units (`"seconds"` or `"samples"`),
  boundary policies (`"nan"`, `"error"`, `"drop"`), and optional event-identity preservation via `return_indices`.
- `ChannelIndexError`: Specific exception raised on continuous channel indexing bounds violations.
- Executable tutorial series: Four tested notebooks and documentation tutorials covering NWB discovery,
  event alignment and PSTH calculation, continuous LFP spectral power with decibel aggregation, and
  Granger directionality.
- Onboarding and harness alignment: Gate 13 pre-flight verification ensuring NWB onboarding terminology,
  workflows, and APIs remain synchronized across README, MkDocs, and task skills.

### Fixed

- Calibrated continuous-channel access: `acquisition_channel` applies physical scaling
  ($x_{\mathrm{physical}} = \mathrm{conversion} \cdot x_{\mathrm{stored}} + \mathrm{offset}$) exactly once,
  preserving physical units inherited from `series.unit` (e.g. Volts).
- 1D continuous array support: `acquisition_channel` gracefully accesses 1D series `(n_samples,)`
  at `channel=0`, raising `ChannelIndexError` for non-zero channel indices.
- Code-agnostic event extraction: `events` and `event_onsets` extract all intervals when `codes=None`
  without requiring a default `"codes"` column.

## [0.1.7] - 2026-09-11

### Fixed

- Monte Carlo p-values use `(b+1)/(B+1)` in `permutation_test`, `shuffle_r2_ci`, and
  jRSA `_p_from_null`; GPU jRSA permutations are seeded from the caller's `Generator`.
- `compare_groups(paired=True)` raises `ValueError` on unequal lengths instead of falling
  back to an independent test.
- `cross_modal_comparison` validates `(freq, time, trials)` / `(time, trials)` layout.
- `spike_mutual_information` bin grid matches `bin_spikes`.
- `granger(order="auto")` IC matches `select_optimal_lag`.
- `granger_spectral` computes per-band surrogate p-values.
- `band_power(normalize=True)` requires a baseline.
- `transfer_entropy(estimator="symbolic")` reports embedded `n_times`.

### Changed

- jRSA metrics renamed to exact estimands: `granger_ssr_ftest`,
  `transfer_entropy_histogram_nats` (legacy names raise with migration hint).
- `granger_causality` deprecated; canonical estimator is `granger` → `DirectedResult`.
- Sdist excludes `tests/` and `scripts/` via `MANIFEST.in`; release/CI forbidden-manifest
  checks enforce the same policy.

### Fixed (final independent audit)

- `granger` VAR order guard accepts `n_obs > n_params` (not `n_obs > n_params + 1`).
- `fit_var_bivariate` / deprecated `granger_causality` raise on undersampled series.
- `UnitAnalyzer.psth` bin grid matches `bin_spikes` (`round` convention).
- `compare_groups(paired=True)` requires at least two pairs.
- `spike_mutual_information` raises on empty spike trains.
- `band_power` raises when the requested band has no Welch bins.
- jRSA CuPy bootstrap CIs seeded from the caller `Generator`.
- Docs: `band_power` examples, `JRSAResult` fields, AGENTS recipe, MCP pointer.

### Closure (second audit RG)

- `jrsa(align='dtw')` raises when `dtw-python` is absent; no silent downsample fallback.
- `jnwb-lfp-spectral` skill routes `band_power`, `aggregate_to_db`, and core filters.
- Removed promotion/subject-ID residue from generic `jnwb/` docstrings and examples.

## [0.1.6] - 2026-09-10

### Changed

- **`import jnwb` defers heavy submodules.** Ontology, statistics, metadata, decoding,
  onset-fitting, analyzer, viz, and `visual_qc` exports resolve through `__getattr__` and
  `jnwb._lazy_exports` so scipy.stats, sklearn, matplotlib, and pynwb are not pulled in
  until a deferred symbol is accessed.
- **`scripts/benchmark_import.py` measures the workspace tree.** Subprocess probes now set
  `PYTHONPATH` to the repository root so an installed site-packages copy cannot mask the
  tree under development. The script reports warm median/mean/stdev, and `--profile` writes
  `artifacts/benchmarks/import_breakdown.json` with importtime attribution.
- **HDMF builder repairs are scoped to jnwb-owned NWB reads** (`jnwb.nwb_io.read_nwb`,
  `nwb_read_io`). `import jnwb` no longer replaces `BuildManager.construct` for the whole
  interpreter. All jnwb package read paths route through the read boundary.
- **Missing `session_description` fails loudly** with `MissingRequiredNWBFieldError` instead
  of inserting a synthetic value.

## [0.1.5] - 2026-09-10

Closes the open GitHub issues: citations, GPU and parallel execution, notebooks, the import
benchmark, and an HSIC defect found while checking one of them.

### Fixed

- **HSIC accepted only 2-D inputs.** `_hsic` flattened `x1` but never `x2`, so `jrsa` with
  1-D, 3-D, or mixed-rank inputs raised `ValueError: XA must be a 2-dimensional array` from
  `cdist`. Both sides are now reshaped to `(n_samples, n_features)`.

### Added

- **`complex_tfr(device='cuda')`** convolves with `cupyx.scipy.signal.fftconvolve`, falls
  back to CPU with a `RuntimeWarning`, and records the device it used on `ComplexTFR.device`.
  64 channels x 10k samples x 40 frequencies: 1.27 s CPU, 0.61 s on an RTX A4000.
- **`directed_network(n_jobs=)`** runs node pairs through `_parallel.parallel_map`. Six
  nodes at `n_jobs=8`: transfer entropy 103.4 s -> 19.6 s, Granger 6.44 s -> 5.28 s. Results
  are identical for any `n_jobs`.
- **`docs/references.md`** — published sources per method with DOIs resolved on Crossref,
  linked from the docs nav. The docstrings of the implementing functions cite the same
  entries.
- **`examples/notebooks/01_spectral_and_inference.ipynb`** on synthetic data, executed in CI
  by `tests/test_notebooks.py` (9.7 s). Needs the `test` extra, which gained `nbclient`,
  `nbformat` and `ipykernel`.
- **`scripts/benchmark_import.py`** measures cold (empty bytecode cache) and warm
  fresh-process imports and rewrites `artifacts/benchmarks/import_profile.txt`: 50445 ms
  cold, 9115 ms warm, 111 public symbols on Python 3.14.3.
- `docs/01_architecture_and_philosophy.md` gained an NWB/PyNWB/HDMF section, and
  `docs/install.md` a GPU and parallel execution section.

## [0.1.4] - 2026-09-10

Closes the boundary defects a review found in 0.1.3: executable code that gave one
project's names meaning, and a gate that passed it.

### Breaking

- **`cross_area_coherence` requires `freq_bands`.** `None` meant `CANONICAL_BANDS`, so the
  band taxonomy behind every band p-value was chosen for the caller. Pass
  `freq_bands='canonical'` to keep 0.1.3 numbers, or a `{name: (fmin, fmax)}` dict.
  `phase_slope_index` already worked this way.
- **MCP `get_event_codes_and_timings` no longer prefers a table named
  `omission_glo_passive`.** With no `event_group_path` it reads `trials`, else the file's
  only interval table, else returns `AmbiguousPath` listing the tables. An explicit path
  that does not exist returns `PathNotFound`; it used to return the first table instead.

### Added

- **Gate 12 (Project Identifiers).** Parses `jnwb/` and fails on any code string or
  identifier containing a project name. Docstrings and comments are skipped. The
  deprecated `OMISSION_*_DIR` variables are the only allowed names. Gates 1 and 6 both
  passed the MCP default above.

### Changed

- `import jnwb` logs a warning when it cannot install its hdmf `BuildManager` repair; the
  failure was silent. The patch is unchanged and still replaces `BuildManager.construct`
  process-wide on import.
- Removed `docs/12_interactive_analyses.md`, which presented one project's analysis and
  results as jnwb documentation.
- Removed project references from two strings in `jnwb/` that Gate 12 flagged.
- `artifacts/context.md` and `docs/memory.md` are folded into `AGENTS.md`, which opens with
  a map of the repository. Four `memory.md` recipes had wrong signatures.

## [0.1.3] - 2026-09-09

Fixes the blocker that made 0.1.1 uninstallable, corrects three defects in
`cross_area_coherence`, renames a path constant that misled every consumer, and removes
a class of silent GPU and import failures. 0.1.2 was never released.

### Breaking

- **`jnwb.paths.REPO_ROOT` is renamed `PACKAGE_ROOT`.** It resolves from `paths.py`'s own
  location, so in a consuming project it named the *jnwb* checkout, not the caller's
  repository, and the path was well-formed enough that nothing failed. One project had 41
  live files building inputs and outputs from it. `REPO_ROOT` still resolves and warns;
  it is removed in 0.2.0. `describe()` reports both keys for this release. To get your own
  root, anchor to your own file.
- **`cross_area_coherence` returns different p-values.** The surrogate draws changed, and
  long signals now draw 50 surrogates instead of 10. Receipts quoting a p-value from this
  function will not reproduce. Pass `n_surrogates=10` for the previous cost.
- **`gpu_pca(device="cuda")` on a machine without CUDA** now computes in float64 NumPy
  rather than float32 torch-on-CPU, and warns. Previously "cpu" meant two different
  precisions depending on which device string you passed.
- **An unrecognised `device` string raises `ValueError`** instead of falling through to
  the CPU unannounced.

### Fixed

- **`requires-python` upper pin (JNWB-001).** 0.1.1 declared `>=3.12, <3.13`, so
  `pip install jnwb==0.1.1` failed on every current interpreter and silently resolved
  users to 0.1.0 -- older code than they asked for. jnwb is a pure-Python `py3-none-any`
  wheel with no ABI reason for a ceiling. Declared support is now `>=3.12` with no upper
  bound, classifiers cover 3.12/3.13/3.14, and CI tests the floor and the newest declared
  version.
- **`cross_area_coherence` surrogate null was unseedable (JNWB-003).** The generator was a
  hardcoded `default_rng(42)` with no parameter, so every caller received the same 50
  surrogates and no seed could be recorded. Adds `rng=`, and returns
  `surrogate_seed_entropy` (`None` when the caller supplied the generator).
- **`cross_area_coherence` could mix estimators inside one null (JNWB-004).** The GPU path
  sat inside the surrogate loop behind a per-iteration `except Exception`, so an
  intermittent failure produced a null assembled from two estimators with nothing logged.
  The device is resolved once; a failure discards partial work and recomputes the observed
  value and the whole null on CPU. The result reports `device_used`.
- **Surrogate count depended on input length (JNWB-005).** `n_surr` dropped from 50 to 10
  above 50,000 samples, making the smallest attainable p-value 1/11 = 0.0909 rather than
  1/51 = 0.0196. At 1 kHz that is 50 s of data, so a caller testing at alpha = 0.05 could
  not reject on a long recording and the return value said nothing. Adds `n_surrogates`
  and returns `n_surrogates_used` and `p_value_floor`.
- **Docstring named the wrong surrogate (JNWB-006).** A circular shift was described as
  phase randomization. Those are different null hypotheses.
- **`jnwb.paths.get_path()` was documented but never existed.** The example now calls
  `nwb_dir()`.

### Added

- **`n_jobs` on `cluster_permutation_test` and `cross_area_coherence`.** Results are
  identical for any `n_jobs`: each iteration is seeded from the caller's generator before
  the loop starts, so worker count cannot change a number. Default is 1 everywhere except
  `jrsa`, which keeps `-1`. Work is dispatched in chunks -- one task per iteration measured
  0.03x, i.e. slower than serial, because process startup dwarfed a 1 ms permutation.
  Chunked: 4.51x on 2000 permutations, 3.08x on 1000 surrogates.
- **Import-shadowing gate.** The editable install writes a `.pth` holding the repository
  root, so any top-level package beside `jnwb/` is importable ahead of a consumer's own
  package of that name, from any working directory (JNWB-002: 88 of 190 importing files in
  one project loaded the wrong copy, disagreeing on an anatomical label, with no error).
  A gate now rejects unowned root packages, and `docs/install.md` documents the hazard and
  the `editable_mode=strict` install.
- **Harness tool definitions are tracked** under `artifacts/agents/`. They were in a
  gitignored `.claude/agents/`, so a fresh clone got none of them. A root `.claude/` now
  fails the gate.
- **New logo** in the README, docs site, and favicon.

### Changed

- **Gate numbering is canonical.** "Gate 9" named two different gates, and "Gate 2",
  "Gate 3" and "Gate 6" were each used twice, so a gate report citing a number was
  ambiguous. Numbers are now the position in `run_full_preflight()`, checked by a test.
- **`check_python_target_consistency` is now `check_python_floor_consistency`.** The old
  gate asserted "3.12 is the sole targeted version" -- the policy that produced JNWB-001 --
  and accepted the upper pin that broke the release. It now asserts that declared support,
  classifiers and CI agree, and rejects any upper bound.
- **One GPU probe.** Fifteen call sites across seven modules each carried their own, some
  treating a bare `import cupy` as proof of a device. CuPy imports fine with no driver, so
  those sites disagreed about the same machine. `jnwb/_backend.py` decides once, and warns
  whenever a requested accelerator cannot be delivered.
- **Sphinx removed.** It built the same markdown a second way and was never published;
  Read the Docs builds mkdocs. `mkdocs build --strict` remains the gate. Removes
  `docs/conf.py`, `docs/_static/`, and three documentation dependencies.
- **One `AGENTS.md`.** The root file and `artifacts/AGENTS.md` were near-duplicates that
  had drifted apart. The root file is jnwb-scoped and carries a tool inventory.
- **Skill counts removed.** `skills/jnwb/SKILL.md` claimed 101 exports against a live 111
  and 446+ tests against 527, and advertised `n_jobs` on functions that lacked it. Counts
  are replaced by the commands that check them, enforced by a test.
- **Thinner repository root.** The root allowlist is split into tracked-source and
  ephemeral directories, and no longer permits `omission` -- the one entry that
  contradicted the import-shadowing gate.

## [0.1.1] - 2026-09-07

### Added
- **Power & Logarithmic Decibel Aggregation**:
  - `aggregate_to_db`: Core statistical primitive to compute arithmetic mean raw power across trials/channels before logarithmic transformation ($10 \log_{10} \mathbb{E}[P]$), guarding against Jensen's inequality bias. Callers must name the estimand (`how="mean_of_ratios"` or `"ratio_of_means"`); geometric-mean aggregation is rejected because it is mean-of-decibels.
- **Landmark electrophysiology primitives**:
  - `compute_multitaper_psd`: DPSS multitaper PSD (Thomson 1982) with one-sided scaling that preserves Parseval variance.
  - `pairwise_phase_consistency`: Vinck et al. (2010) unbiased phase-synchronization estimator, independent of spike count.
  - `gaussian_smooth_rate`: Acausal Gaussian PSTH smoothing, distinct from causal exponential smoothing.
  - `voltage_curvature_1d` / `current_source_density_1d`: Discrete second spatial derivative in V/m², and physical 1D CSD in A/m³ with required conductivity (S/m).
  - `cluster_permutation_test`: Maris & Oostenveld (2007) cluster FWER control with paired sign-flip, independent label shuffle, and within-group exchangeability.
  - SOS Butterworth `bandpass_filter` and IIR `notch_filter` with explicit zero-phase vs causal modes.
- **Documentation & Figures**:
  - 10 deterministic executable scientific figures (`docs/assets/figures/`) generated directly by `docs/generate_figures.py` using public jnwb APIs.
  - `docs/common_mistakes.md`: Guide to common electrophysiology pitfalls (Jensen's inequality, right-open bins, exchangeability, CV leakage, channel ID vs. index, causality vs. predictability, PSI bandwidth, causal filter delay).

### Changed
- **Boundary Semantics**:
  - `fires_in_window` and `rate_in_window` in `jnwb/statistics.py`: Enforced strict right-open intervals $[t_0, t_1)$ using left-side binary searches at both boundaries, preventing double-counting across contiguous time bins.
  - `compute_response_metrics` in `jnwb/spiking.py`: Enforced strict right-open intervals $[t_0, t_1)$ for baseline and response windows.
  - `bin_spikes` in `jnwb/connectivity.py`: Explicit right-open binning semantics $B_k = [t_0 + k\Delta, t_0 + (k+1)\Delta)$ with exact centers $c_k = t_0 + (k + 1/2)\Delta$.
- **Path Resolution & Packaging**:
  - `jnwb/paths.py`: Repaired `outputs_dir()` to avoid resolving into `site-packages` when installed, prioritizing explicit overrides and `JNWB_OUTPUTS_DIR` environment variable with clean local fallback.
  - `pyproject.toml`: Conformed license metadata to PEP 621 table specification (`license = { text = "MIT" }`).
- **Public return keys**:
  - `paired_fire_prob_test` reports the paired control rate as `p_fire_baseline` (replacing the dataset-specific `p_fire_pre_omission_baseline`).

### Fixed
- **Addressing & Indexing**:
  - `jnwb/addressing.py`: Repaired channel ID vs. DataFrame integer row index conflation in `_resolve_electrode_row` and multi-area probe partitioning.
- **Numerical Safety**:
  - `jnwb/spectral.py`: Repaired `spectral_tilt` numerical stability, guarding against flat/zero PSDs and non-positive powers.
- **Cluster permutation**:
  - `cluster_permutation_test` reported each observed cluster twice (copy-paste duplicate append). Tests now assert unique cluster masks.
- **Release verification**:
  - CI no longer hardcodes a stale public-export count (was 101; live surface is 111).
  - Local `scripts/release_gate.py` now uses a venv without `--system-site-packages` and installs the wheel with declared dependencies.
  - `scripts/harness_gate.py` puts the repository root on `sys.path` before importing `jnwb`, so documentation completeness is checked against the candidate rather than a leftover site-packages install.

## [0.1.0] - 2026-09-01

### Added
- **Core Signal & Spectral Primitives**:
  - `complex_tfr`: Complex Morlet wavelet transform with discrete $L_1$ amplitude normalization and Cone of Influence (COI) boundary validity masking.
  - `ComplexTFR`: Dataclass container providing `z`, `power`, `phase`, `amplitude`, `freqs`, `times`, and `coi_mask`.
  - `compute_psd`, `band_power`, `spectral_tilt`, `cross_area_coherence`, `imaginary_coherency`.
  - `phase_locking_value`, `bipolar_reference`, `laplacian_reference`.
- **Streaming & Accumulation**:
  - `TFRAccumulator`: Welford running variance, mean power, Inter-Trial Coherence (ITC), evoked power, and induced power.
  - `assert_mergeable`: Schema verification for merging streaming TFR datasets.
- **Spiking & Onset Dynamics**:
  - `raster_psth`, `compute_response_metrics`, `phase_locking_index`, `cross_correlation`.
  - `causal_exp_smooth`: Causal single-pole exponential filter with tau compensation.
  - `fit_exponential_onset`: Single-unit onset latency estimator with `bound_status` censoring detection.
- **Resampling Statistics & Hypothesis Testing**:
  - `StatisticalAnalysis`: `bootstrap_ci`, `paired_fire_prob_test`, `confirmatory_compare`.
  - `exploratory_compare`: Clean dual reporting of parametric and nonparametric metrics.
  - `permute_labels`: Label permutation with `'global'` and `'within_group'` support.
  - `fdr_correct`, `bonferroni_correct`.
- **Directed Connectivity & Information Theory**:
  - `granger`: Time-domain bivariate Granger causality with permutation surrogates.
  - `phase_slope_index`: Phase Slope Index with analytical standard error.
  - `transfer_entropy`: Bivariate Transfer Entropy with lag embedding.
- **Decoding & Population Dynamics**:
  - `nested_cv_linear_svm`: Nested cross-validated linear SVM classifier.
  - `compute_population_trajectory`, `time_resolved_trajectory`.
- **Artifact Detection & Repair**:
  - `channel_correlation_matrix`, `detect_flat_or_noisy_channels`, `detect_extreme_events`.
  - `repair_lfp_trials`: Outlier thresholding and cross-channel linear interpolation repair.
- **Anatomical Addressing & Ontology**:
  - `map_peak_channel_to_area`, `classify_layer_from_depth`, `enrich_units_dataframe`.
- **Publication Graphics**:
  - `setup_vector_graphics`, `apply_tight_auto_axis`, `save_figure_suite`.
- **Packaging & CI**:
  - PEP 621 `pyproject.toml` with SPDX MIT license.
  - ReadTheDocs configuration (`.readthedocs.yaml`, `docs/conf.py`).
  - GitHub Actions CI workflow supporting Python 3.10 through 3.14.
  - Deterministic release gate (`scripts/release_gate.py`).
