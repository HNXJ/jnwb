# Sampling-rate checks and `_require_*` helpers in jnwb/ (todo 17-94 residual)

Baseline: 2a1814a0488f03c46d4e65d766d0b5aa168d861b (HEAD matched; tree clean). Read-only.
Table A rows: `git grep -nE "fs <= 0|fs > 0|isfinite\(fs\)|fs must|require_positive_fs" -- jnwb/` (52 hits).
Table B rows: `git grep -nE "def _require_" -- jnwb/` (21 defs).
Test pins: `git grep` over tracked files under `tests/`, substring match on the quoted text.

## Table A: fs checks (one row per grep hit)

Row kinds: a raise is two rows (condition row, message row). Rows that are only an import, a docstring, a definition, or a grep false match are NOT-A-CHECK. "(see N)" points to the row holding the message.

| file:line | function | exact condition | exact error text and type | NaN/Inf refused | test pins exact text | class |
|---|---|---|---|---|---|---|
| jnwb/_units.py:24 | require_positive_fs (def) | n/a (definition) | n/a | n/a | n/a | NOT-A-CHECK |
| jnwb/_units.py:32 | require_positive_fs (docstring) | n/a (docstring text "passes `fs <= 0`") | n/a | n/a | n/a | NOT-A-CHECK |
| jnwb/_units.py:38 | require_positive_fs | `float(fs)` raises TypeError or ValueError | ValueError `{func_name}: fs must be a number in Hz; got {fs!r}.` | no here (refused at 40-42) | yes, substring "fs must be a number in Hz": tests/test_fs_nonfinite.py:31, 33 | CANONICAL (helper body) |
| jnwb/_units.py:42 | require_positive_fs | `not np.isfinite(value) or value <= 0.0` | ValueError `{func_name}: fs must be finite and strictly positive (Hz); got {fs!r}.` | yes | yes, substring "fs must be finite and strictly positive": tests/test_api_consistency.py:229, 249 | CANONICAL (helper body) |
| jnwb/analyzers.py:85 | TFRAnalyzer.extract_band | `band_defs is not None and len(band_defs) == 0` (not an fs check) | ValueError `band_defs must not be empty; pass None for the default bands.` | n/a | no for fs; the text is pinned by tests/test_analyzers_coverage.py:111 | NOT-A-CHECK (grep match "band_defs must") |
| jnwb/connectivity/_granger.py:1020 | granger_spectral | `fs is None or not np.isfinite(fs) or fs <= 0` | ValueError `granger_spectral requires a positive fs; got {fs!r}` | yes | no | SAME-CHECK |
| jnwb/connectivity/_granger.py:1278 | granger_nonparametric | `fs is None or not np.isfinite(fs) or fs <= 0` | ValueError `granger_nonparametric requires a positive fs; got {fs!r}` | yes | yes, substring "positive fs" (fs 0.0, -1.0, nan, inf): tests/test_connectivity.py:1606 | DIFFERENT-MESSAGE |
| jnwb/connectivity/_psi.py:498 | phase_slope_index | `fs is None or not np.isfinite(fs) or fs <= 0` | ValueError `phase_slope_index requires a positive fs; got {fs!r}` | yes | no | SAME-CHECK |
| jnwb/continuous.py:136 | epoch_continuous | `not (np.isfinite(fs) and fs > 0.0)` (condition of 137) | n/a (see 137) | yes | n/a | DIFFERENT-MESSAGE (see 137) |
| jnwb/continuous.py:137 | epoch_continuous | `not (np.isfinite(fs) and fs > 0.0)` | ValueError `Sampling rate fs must be positive, got {fs}` | yes | yes, substring: tests/test_fs_nonfinite.py:24 (nan, inf, -inf); tests/test_continuous.py:236 ("must be positive", fs=0.0) | DIFFERENT-MESSAGE |
| jnwb/filtering.py:12 | module | import of require_positive_fs | n/a | n/a | n/a | NOT-A-CHECK (import) |
| jnwb/filtering.py:33 | bandpass_filter | `require_positive_fs(fs, "bandpass_filter")` | via helper: ValueError `bandpass_filter: fs must be finite and strictly positive (Hz); got {fs!r}.` | yes | yes, substring "bandpass_filter: fs must be finite": tests/test_fs_nonfinite.py:10 | ALREADY-USES-HELPER |
| jnwb/filtering.py:77 | notch_filter | `require_positive_fs(fs, "notch_filter")` | via helper: ValueError `notch_filter: fs must be finite and strictly positive (Hz); got {fs!r}.` | yes | yes, substring "notch_filter: fs must be finite": tests/test_fs_nonfinite.py:17 | ALREADY-USES-HELPER |
| jnwb/laminar/_vflip.py:980 | vflip_from_lfp | `fs <= 0 or not np.isfinite(fs)` (after `fs = float(fs)`) | n/a (see 981) | yes | n/a | DIFFERENT-MESSAGE (see 981) |
| jnwb/laminar/_vflip.py:981 | vflip_from_lfp | `fs <= 0 or not np.isfinite(fs)` | ValueError `fs must be strictly positive and finite (Hz), got {fs}` | yes | yes, prefix "fs must be strictly positive": tests/test_laminar.py:458 (fs=-100.0), 461 (fs=nan) | DIFFERENT-MESSAGE |
| jnwb/laminar/_vflip2.py:526 | vflip2_from_lfp | `isinstance(fs, bool) or not isinstance(fs, (int, float, np.integer, np.floating))` | ValueError `fs must be a real number, got {fs!r}` | no (NaN is a float; refused at 528) | prefix only "fs must be": tests/test_vflip2_from_lfp.py:120 (True, "1000") | SPECIALIZED (type gate) |
| jnwb/laminar/_vflip2.py:528 | vflip2_from_lfp | `not (np.isfinite(fs) and fs > 0)` (condition of 529) | n/a (see 529) | yes | n/a | SAME-CHECK (see 529) |
| jnwb/laminar/_vflip2.py:529 | vflip2_from_lfp | `not (np.isfinite(fs) and fs > 0)` | ValueError `fs must be finite and positive, got {fs}` | yes | prefix only "fs must be": tests/test_vflip2_from_lfp.py:120 (0, -1000.0, nan, inf); the prefix also fits the helper text | SAME-CHECK |
| jnwb/laminar/_vflip2.py:532 | vflip2_from_lfp | `fs / 2 < 150` (fs already finite and > 0 at 528) | ValueError `vflip2_from_lfp: fs must be at least 300 Hz, so that the Nyquist frequency fs / 2 reaches the 150 Hz band edge; got fs={fs:g}` | yes (via 528) | yes, substring "at least 300 Hz": tests/test_vflip2_from_lfp.py:147 (fs=250.0) | SPECIALIZED (150 Hz band edge) |
| jnwb/laminar/_zflip.py:257 | _check_rate_and_input | `fs <= 0 or not np.isfinite(fs)` (condition of 258) | n/a (see 258) | yes | n/a | DIFFERENT-MESSAGE (see 258) |
| jnwb/laminar/_zflip.py:258 | _check_rate_and_input | `fs <= 0 or not np.isfinite(fs)` | ValueError `fs must be strictly positive and finite; got {fs}.` | yes | prefix "fs must be strictly positive": tests/test_zflip.py:96 (fs=-10.0; NaN not tested) | DIFFERENT-MESSAGE |
| jnwb/laminar/_zflip.py:614 | zflip (docstring) | n/a (docstring "`fs <= 0`") | n/a | n/a | n/a | NOT-A-CHECK (docstring) |
| jnwb/laminar_curation.py:175 | detect_bad_channels | `not np.isfinite(fs) or fs <= 0` (after `fs = float(fs)`) | n/a (see 176) | yes | n/a | SAME-CHECK (see 176) |
| jnwb/laminar_curation.py:176 | detect_bad_channels | `not np.isfinite(fs) or fs <= 0` | ValueError `fs must be positive and finite, got {fs!r}` | yes | no | SAME-CHECK |
| jnwb/spectral/__init__.py:33 | module | import re-export of `_require_positive_fs` | n/a | n/a | n/a | NOT-A-CHECK (import) |
| jnwb/spectral/_common.py:6 | module | import alias of require_positive_fs | n/a | n/a | n/a | NOT-A-CHECK (import) |
| jnwb/spectral/_common.py:85 | _resolve_fs | `fs is not None and sampling_rate is not None` and `fs == sampling_rate`; calls helper(fs) | via helper (helper text) | yes | helper text pinned by tests/test_api_consistency.py:229, 249 (callers of _resolve_fs not traced) | ALREADY-USES-HELPER |
| jnwb/spectral/_common.py:87 | _resolve_fs | `fs is not None`; calls helper(fs) | via helper (helper text) | yes | as 85 | ALREADY-USES-HELPER |
| jnwb/spectral/_common.py:89 | _resolve_fs | `sampling_rate is not None`; calls helper(sampling_rate) | via helper (helper text) | yes | as 85 | ALREADY-USES-HELPER |
| jnwb/spectral/_psd.py:16 | module | import alias of require_positive_fs | n/a | n/a | n/a | NOT-A-CHECK (import) |
| jnwb/spectral/_psd.py:74 | compute_psd | `not (np.isfinite(fs) and fs > 0)` (condition of 75) | n/a (see 75) | yes | n/a | DIFFERENT-MESSAGE (see 75) |
| jnwb/spectral/_psd.py:75 | compute_psd | `not (np.isfinite(fs) and fs > 0)` | ValueError `compute_psd: fs must be positive and finite, got {fs}.` | yes | yes, substring "positive and finite" (fs 0.0, -1000.0, nan, inf): tests/test_spectral.py:125 | DIFFERENT-MESSAGE |
| jnwb/spectral/_psd.py:786 | compute_multitaper_psd | `_require_positive_fs(fs, "compute_multitaper_psd")` | via helper: ValueError `compute_multitaper_psd: fs must be finite and strictly positive (Hz); got {fs!r}.` | yes | yes, substring "compute_multitaper_psd: fs": tests/test_spectral.py:775; "strictly positive": tests/test_spectral.py:750 | ALREADY-USES-HELPER |
| jnwb/statistics/_tests.py:156 | exact_sign_flip | `not np.all(np.isfinite(arr))` on `diffs` (not fs) | ValueError `diffs must contain only finite numerical values (no NaN or Inf)` | yes (diffs) | no | NOT-A-CHECK (grep match "diffs must") |
| jnwb/testing/synth.py:121 | synth_ar_noise | `fs <= 0 or not np.isfinite(fs)` (condition of 122) | n/a (see 122) | yes | n/a | SAME-CHECK (see 122) |
| jnwb/testing/synth.py:122 | synth_ar_noise | `fs <= 0 or not np.isfinite(fs)` | ValueError `fs must be strictly positive, got {fs}` | yes | no | SAME-CHECK |
| jnwb/testing/synth.py:202 | synth_periodic_response | `fs <= 0 or not np.isfinite(fs)` (condition of 203) | n/a (see 203) | yes | n/a | SAME-CHECK (see 203) |
| jnwb/testing/synth.py:203 | synth_periodic_response | `fs <= 0 or not np.isfinite(fs)` | ValueError `fs must be strictly positive, got {fs}` | yes | no | SAME-CHECK |
| jnwb/testing/synth.py:334 | synth_phase_gradient | `fs <= 0 or not np.isfinite(fs)` (condition of 335) | n/a (see 335) | yes | n/a | SAME-CHECK (see 335) |
| jnwb/testing/synth.py:335 | synth_phase_gradient | `fs <= 0 or not np.isfinite(fs)` | ValueError `fs must be strictly positive, got {fs}` | yes | no | SAME-CHECK |
| jnwb/testing/synth.py:424 | synth_laminar_motif | `n_samples <= 0 or fs <= 0` (condition of 425) | n/a (see 425) | no (NaN passes `fs <= 0`) | n/a | SAME-CHECK (see 425; helper would add NaN refusal) |
| jnwb/testing/synth.py:425 | synth_laminar_motif | `n_samples <= 0 or fs <= 0` | ValueError `n_samples and fs must be positive` | no | no | SAME-CHECK |
| jnwb/testing/synth.py:553 | synth_vflip2_crossover | `fs <= 0 or not np.isfinite(fs)` (condition of 554) | n/a (see 554) | yes | n/a | SAME-CHECK (see 554) |
| jnwb/testing/synth.py:554 | synth_vflip2_crossover | `fs <= 0 or not np.isfinite(fs)` | ValueError `fs must be strictly positive, got {fs}` | yes | no | SAME-CHECK |
| jnwb/tfr.py:130 | morlet_wavelet | `not np.isfinite(fs)` (condition of 131) | n/a (see 131) | yes | n/a | SAME-CHECK (half of the helper condition; see 131) |
| jnwb/tfr.py:131 | morlet_wavelet | `not np.isfinite(fs)` | ValueError `fs must be finite, got {fs}` | yes | weak: tests/test_nonfinite_inputs.py:803 asserts only "fs" in the message (nan, inf) | SAME-CHECK |
| jnwb/tfr.py:132 | morlet_wavelet | `fs <= 0` (reached after 130-131) (condition of 133) | n/a (see 133) | yes (after 130) | n/a | SAME-CHECK (half; see 133) |
| jnwb/tfr.py:133 | morlet_wavelet | `fs <= 0` | ValueError `fs must be positive, got {fs}` | yes (after 130) | no (tests/test_complex_tfr.py:171, 173 reach complex_tfr:256 first) | SAME-CHECK |
| jnwb/tfr.py:255 | complex_tfr | `fs <= 0` (condition of 256) | n/a (see 256) | no | n/a | DIFFERENT-MESSAGE (see 256) |
| jnwb/tfr.py:256 | complex_tfr | `fs <= 0` | ValueError `fs must be positive, got {fs}` | no at this site; NaN reaches morlet_wavelet (tfr.py:306), which refuses it (tfr.py:131) | yes, prefix "fs must be positive": tests/test_complex_tfr.py:171, 173 (fs=0.0, -100.0) | DIFFERENT-MESSAGE |
| jnwb/wavemap.py:134 | align_waveforms | `not (np.isfinite(fs) and fs > 0)` (condition of 135) | n/a (see 135) | yes | n/a | SAME-CHECK (see 135) |
| jnwb/wavemap.py:135 | align_waveforms | `not (np.isfinite(fs) and fs > 0)` | ValueError `align_waveforms: fs must be a finite positive number; got {fs!r}.` | yes | no | SAME-CHECK |

Table A class counts (rows, 52 total): NOT-A-CHECK 9; CANONICAL 2; ALREADY-USES-HELPER 6; SAME-CHECK 22; DIFFERENT-MESSAGE 11; SPECIALIZED 2. Sum 52.
Logical raises (a condition and its message count once): SAME-CHECK 12; DIFFERENT-MESSAGE 6; SPECIALIZED 2; ALREADY-USES-HELPER 6 call sites; CANONICAL 1.

## Table B: `_require_*` helper definitions (one row per def)

Error texts abbreviated with "..." where long. Full text at the file:line.

| file:line | signature | what it checks | error text | caller count | class |
|---|---|---|---|---|---|
| jnwb/compression.py:107 | `_require_selection(select) -> None` | `select is None` | TypeError "select= is required: pass the floating-point dataset paths ..." | 3 (compression.py:130, 611, 995) | SPECIALIZED |
| jnwb/jrsa/_inference.py:15 | `_require_null(null, block_len)` | null not None and not in NULL_SCHEMES; null "block" needs block_len a positive int (bool refused) | ValueError "jrsa: unrecognized null ..." and "jrsa: null='block' needs block_len ..." | 1 (jrsa/__init__.py:560) | SPECIALIZED |
| jnwb/jrsa/_inference.py:167 | `_require_alternative_exact(alternative)` | alternative not in ALTERNATIVES, case-sensitive, no strip | ValueError "jrsa: unrecognized alternative {alternative!r}. ..." | 2 (jrsa/__init__.py:559; jrsa/_inference.py:217) | REDUNDANT-WITH _require_alternative_casefold (same set ('two-sided','greater','less'); case rule differs) |
| jnwb/jrsa/_metrics.py:100 | `_require_same_rows(metric, X, Y)` | `X.shape[0] != Y.shape[0]` | ValueError "{metric}: x1 has {n} rows and x2 has {m}; ..." | 5 (_metrics.py:134, 171, 215, 244, 289) | REDUNDANT-WITH _require_equal_lengths (same condition for arrays, len(X) == X.shape[0]; message differs) |
| jnwb/jrsa/_metrics.py:357 | `_require_one_series(x, metric, trial_function)` | `prod(x.shape[:-1]) > 1` | ValueError "jrsa(metric=...) takes one series per input; ..." | 3 (_metrics.py:315, 405, 464) | SPECIALIZED |
| jnwb/jrsa/_metrics.py:373 | `_require_paired_shape(x1, x2, metric)` | `x1.shape != x2.shape` (full shape) | ValueError "jrsa(metric=...) pairs the samples of x1 and x2 one to one, ..." | 4 (_metrics.py:270, 316, 406, 465) | SPECIALIZED (full shape; equals _require_equal_lengths for 1-D only) |
| jnwb/laminar/_zflip.py:157 | `_require_accepted_vflip2(result, argument) -> None` | `not result.accepted`; or proximal/distal channel None; or orientation not in map | ValueError "zflip refuses a rejected vflip2 result as {argument}: ..." and "... with no window as {argument}: ..." | 2 (_zflip.py:181, 211) | SPECIALIZED |
| jnwb/nam.py:42 | `_require_torch()` | `not _TORCH_AVAILABLE` | ImportError "jnwb.nam requires PyTorch. Install optional torch dependencies via: pip install 'jnwb[torch]'" | 4 (nam.py:53, 91, 99, 116) | REDUNDANT-WITH _require_extra (optional-dependency gate; probe differs) |
| jnwb/nwb_write.py:1137 | `_require_session_description(handle: h5py.File) -> None` | `session_description` missing or not a Dataset | MissingRequiredNWBFieldError("session_description"); class at jnwb/nwb_io.py:77, message not traced | 1 (nwb_write.py:1559) | SPECIALIZED |
| jnwb/spectral/_common.py:9 | `_require_band_bins(freqs, mask, freq_range, func_name) -> None` | `not np.any(mask)` (no bin in range) | ValueError "{func_name}: freq_range ... contains no bin of the frequency grid ..." | 4 (_coupling.py:1033, 1186; _psd.py:205, 351) | SPECIALIZED |
| jnwb/spectral/_common.py:22 | `_require_finite_nonempty_trace(x, func_name, name="lfp_trace") -> np.ndarray` | size 0; or not all finite | ValueError "{func_name}: {name} is empty; ..." and "{func_name}: {name} must be finite; ..." | 5 (_decibels.py:419, 426; _psd.py:73, 163, 309) | REDUNDANT-WITH _require_finite_nonempty_pair (same empty and finite tests, per trace) |
| jnwb/spectral/_common.py:38 | `_require_two_samples(arr, func_name, name="lfp_trace") -> np.ndarray` | `arr.shape[-1] < 2` | ValueError "{func_name}: {name} has {n} sample(s) along its last axis; ..." | 4 (_decibels.py:418, 425; _psd.py:162, 308) | SPECIALIZED |
| jnwb/spectral/_coupling.py:20 | `_require_equal_lengths(x, y, func_name) -> None` | `len(x) != len(y)` | ValueError "{func_name}: x and y must have the same length, got {n} and {m}. ..." | 3 (_coupling.py:685, 686, 1005) | SPECIALIZED |
| jnwb/spectral/_coupling.py:36 | `_require_1d_pair(x, y, func_name) -> None` | `np.asarray(trace).ndim != 1` for x and y | ValueError "{func_name} x must be a 1-D time series, got shape ..." (and y) | 2 (_coupling.py:1002, 1131) | SPECIALIZED |
| jnwb/spectral/_coupling.py:53 | `_require_finite_nonempty_pair(x, y, func_name) -> None` | `len(x) == 0`; or x or y not all finite | ValueError "{func_name}: x and y are empty; ..." and "{func_name}: x and y must be finite. ..." | 5 (_coupling.py:430, 683, 684, 1006, 1135) | SPECIALIZED (two-input form; see _require_finite_nonempty_trace) |
| jnwb/spectral/_coupling.py:99 | `_require_identifiable_segmentation(n_samples, nperseg, noverlap, func_name, quantity) -> int` | `welch_segment_count(...) < MIN_IDENTIFIABLE_SEGMENTS` | ValueError "{func_name}: {quantity} is not identifiable from {n} Welch segment(s) ..." | 4 (laminar/_zflip.py:299; _coupling.py:702, 1014, 1143) | SPECIALIZED |
| jnwb/spectral/_reference.py:9 | `_require_channel_permutation(channel_order, n_channels, func_name) -> np.ndarray` | 1-D; integer dtype; length == n_channels; sorted == arange(n_channels) | four ValueErrors: "channel_order must be 1-D ...", "... must be an integer index array ...", "... has N entries for M channels ...", "... must be a permutation of range(n) ..." | 2 (_reference.py:76, 124) | SPECIALIZED |
| jnwb/statistics/_analysis.py:70 | `_require_draws(count, func_name, name) -> None` | `count < 1` | ValueError "{func_name}: {name} must be >= 1, got {count}" | 6 (_analysis.py:179, 256, 578, 659, 763, 860) | REDUNDANT-WITH _require_shuffle_inputs (partial: its n_shuffles arm, `n_shuffles < 1`, also checks bool and int type) |
| jnwb/statistics/_tests.py:215 | `_require_shuffle_inputs(a, b, n_shuffles, func_name) -> None` | a or b not all finite; n_shuffles bool, non-integer, or < 1 | ValueError "{func_name}: a and b must be finite; ..." and "{func_name}: n_shuffles must be a positive integer, got ..." | 3 (statistics/_regression.py:62; _tests.py:292, 353) | SPECIALIZED |
| jnwb/statistics/_tests.py:305 | `_require_alternative_casefold(alternative, func_name) -> str` | `str(alternative).strip().lower()` not in ('two-sided','greater','less') | ValueError "{func_name}: alternative must be one of 'two-sided', 'greater', 'less'; got ..." | 2 (_tests.py:293, 354) | REDUNDANT-WITH _require_alternative_exact (same set; this one strips and case-folds) |
| jnwb/wavemap.py:94 | `_require_extra(func_name)` | `import networkx` and `import umap` both succeed | ImportError "{func}: needs umap-learn and networkx; install them with `pip install jnwb[wavemap]`." | 2 (wavemap.py:292, 359) | REDUNDANT-WITH _require_torch (optional-dependency gate; probe differs) |

Table B class counts (21 defs): SPECIALIZED 14; REDUNDANT-WITH 7 (_require_alternative_exact, _require_same_rows, _require_torch, _require_finite_nonempty_trace, _require_draws, _require_alternative_casefold, _require_extra). Sum 21.

## Notes

- Classes outside the packet's enum: NOT-A-CHECK (def, docstring, import, grep false match) and CANONICAL (the helper body). Both are labelled so the enum counts sum to the row count.
- SAME-CHECK is read as: same condition and error type, and no test pins the message text. The packet's "identical message" cannot hold for any unpinned site, so a replacement would change the message. Whether that is acceptable is the owner's call.
- The NaN column is the row's own check; a refusal by a later line is named in the cell.
- "Test pins" is a substring test over tracked files under tests/. Prefix and substring pins are labelled. A pin on a helper's text is credited to the helper, and callers were not traced for it (see unresolved).
- The `_require_` count is 21 by `def _require_` (unanchored) and by `^def _require_`, the same set. `require_channel_major` and `require_trial_length` in jnwb/_layout.py and `require_positive_fs` have no underscore and are outside Table B.

## Could not determine

- Table A scope: the packet's grep covers only the listed phrases. Other fs checks are not inventoried, e.g. `_resolve_fs` "requires sampling rate `fs`" (jnwb/spectral/_common.py:90, pinned by tests/test_spectral.py:698-710), the `waveform_halfwidth` fs check (pinned by tests/test_unit_quality.py:442, match "fs"), and the "integer fs" pin in tests/test_vflip2_from_lfp.py:99 (no matching site found in this grep).
- Table B: the MissingRequiredNWBFieldError message text (jnwb/nwb_io.py:77, not read further). Caller counts are text matches of `_require_<name>` outside the definition and import lines, not traced execution paths.
- Table A: which public functions reach `_resolve_fs` in tests/test_api_consistency.py:229, 249 (not traced).
