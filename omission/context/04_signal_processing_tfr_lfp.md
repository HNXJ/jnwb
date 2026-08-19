# 04 — Signal Processing: TFR, LFP, Connectivity

Generated 2026-08-17.

## `jnwb/spectral.py` (649 lines) — Welch/CSD band and coherence analysis

No Morlet/wavelet TFR generation lives here — this module is exclusively Welch/CSD band-power
and coherence analysis on single continuous traces. TFR `(trial, channel, freq, time)` array
generation lives in `scripts/` (below), not in `jnwb`.

- **`to_db(ratio)`** (line 26) — the single canonical `10*log10(ratio)` call site, promoted
  2026-08-14 from duplicated inline call sites, enforcing CLAUDE.md tripwire #3 ("log last").
- **`harmonic_analysis()`** — Welch PSD (hann, `nperseg=min(len,4096)`) → fundamental peak +
  integer-multiple harmonics (±10% tolerance). Single 1-D trace, not TFR-based.
- **`cross_area_coherence()`** — `scipy.signal.coherence` (magnitude-squared, Welch-based)
  between two 1-D LFP traces. Default `freq_bands = connectivity.CANONICAL_BANDS`. **Intentional
  break, 2026-08-04**: this default replaced a pre-correction band set (delta 1-4, alpha 8-12,
  beta 12-30, low_gamma 30-55, high_gamma 55-90) — pass `freq_bands=` explicitly to reproduce
  old output. Band coherence = `np.mean(coherency[mask])` (linear-domain, no log). Significance:
  phase-randomization surrogate (n_surr=50, or 10 if len>50000).
- **`spectral_tilt()`** — 1/f exponent via `np.polyfit` on log10(freq) vs log10(power), Welch PSD,
  default range 1-100 Hz.
- **`band_power()`** — the key dB-convention function. Welch PSD → `band_power_val =
  np.mean(pxx[mask])` (linear, per-trace) → if `normalize=True` and `baseline` given, same for
  the baseline trace → `10*log10(band/baseline)` applied **once**, after both frequency-axis
  averages. This matches "log last" for the frequency axis, because the function only ever sees
  one trace and divides-then-logs exactly once. **Caveat**: `band_power()` does no trial/channel
  averaging itself — if a caller invokes it per-trial and then averages the returned dB values
  across trials, *that caller* violates tripwire #3, not this function. No such call site was
  found inside `jnwb/spectral.py` itself in this audit.
- **`imaginary_coherency()`** — Nolte et al. 2004 Im(coherency) between two continuous signals
  (Welch/CSD, `nperseg=min(n,1024)`). Returns `icoh_mean` (signed, band-averaged), `icoh_abs_mean`
  (never cancels), `coh_mag_mean` (large gap vs icoh flags volume-conduction-dominated raw
  coherence). Required for the fig06/fig07 volume-conduction control. Callers must re-reference
  (bipolar/Laplacian) first — this controls for, doesn't replace, reducing zero-lag mixing
  upstream. Validated in `scripts/validate_imaginary_coherency.py`.
- **`bipolar_reference()` / `laplacian_reference()`** — depth-order re-referencing, run before
  any coupling estimate.
- **`_welch_csd_gpu()`** — CuPy Welch/CSD helper with **no CPU fallback inside itself**; every
  caller wraps it in try/except. Not the pattern to copy elsewhere per `omission-signal` skill.

`CANONICAL_BANDS` (imported from `connectivity.py`, no duplicate here): theta 4-8, alpha 8-14,
beta 14-30, low_gamma 30-50, high_gamma 50-80 — the "settled" table. See doc02 for the four-way
band-definition fragmentation across the rest of the package.

## `jnwb/connectivity.py` (2022 lines) — MI, Granger, directed connectivity

Shared contract: `as_trials()` normalizes 1D/2D/ragged input to `(n_trials, n_times)`, hard-errors
on 3D+ or non-finite samples (no silent NaN imputation). `DirectedResult` is the uniform return
type for every directed estimator.

- **Undirected MI**: `spike_mutual_information` (discrete Shannon MI, bits) — `binary_occupancy`
  vs `spike_count` estimators, plug-in, no bias correction, no built-in significance test.
- **Granger (time-domain, bivariate)**: legacy `granger_causality()` and modern `granger()`.
  Restricted-vs-unrestricted VAR(p), `GC = log(var_restricted/var_unrestricted)`. `granger()`
  supports conditioning (partial Granger), ridge-penalized OLS, AIC/BIC/HQIC lag selection
  (BIC default), zscore-detrend default. Analytic F-test p-value by default; optional
  trial-shuffle surrogate for non-white residuals. Sign: `x_to_y` = X's past helps predict Y.
  **Diagnostics** (`_series_diagnostics`): lightweight Dickey-Fuller-style unit-root test (OLS
  t-stat, asymptotic — not a full ADF table) + Ljung-Box residual-autocorrelation test (first
  trial's residual block only, avoids spurious cross-trial-boundary autocorrelation), collected
  into `diagnostics['warnings']`; `ok_for_interpretation = len(warnings)==0`.
- **Spectral (Geweke) Granger**: `granger_spectral()` — fits the same bivariate VAR as
  `granger()`, decomposes in frequency domain via transfer function + noise covariance (Geweke
  1982). **Not** Wilson spectral factorization. Band-passing the input then calling plain
  `granger()` does **not** give band-resolved directionality (filtering distorts the lag
  structure) — must use this decomposition instead. `_var_spectral_radius() >= 1` flags
  non-stationary fit.
- **Phase Slope Index**: `phase_slope_index()` — Nolte et al. 2008; antisymmetric by construction
  (`psi(X,Y) = -psi(Y,X)` exactly — one test, not two, `p_x_to_y == p_y_to_x` deliberately).
  Needs power spread across a band — a near-pure tone gives PSI≈0 regardless of true delay
  (documented check: 14-30Hz band-limited noise delayed 10ms → z=64, vs 20Hz pure sinusoid same
  delay → z=3). Volume-conduction robust by construction.
- **Transfer entropy**: `transfer_entropy()` — model-free, `TE(X→Y) = I(Y_t; X_past | Y_past)`,
  optional Miller-Madow bias correction (default). Positively biased at finite N — raw TE>0
  alone means nothing; default `n_surrogates=200` reports raw + bias-corrected + surrogate
  p-value. Expensive: 200 surrogates is impractical for a full network; 15-30 is a disclosed
  runtime/validity tradeoff that must be stated, not silently chosen.
- **Dispatcher**: `directed_connectivity(X, Y, method=...)`; `directed_network()` — all-pairs
  network, BH-FDR across the **whole N×(N-1)** ordered-pair family by default.

**PLV / imaginary coherence — retired location**: `jnwb/_unused/complex_tfr.py` (quarantined, not
importable as `jnwb.complex_tfr`). The `omission-signal` skill's example import of
`jnwb.complex_tfr` is stale — see doc09.

## TFR output products on disk

`jnwb.paths.tfr_dir()` resolves precomputed TFR arrays to `<analysis_dir>/tfr_arrays` on the
**external volume** (default `D:/analysis/tfr_arrays`), not under `outputs/`. Filename
convention: `{session_prefix}-{probe_letter}-{area}-{condition}.npy`, shape
`(n_trials, n_channels, n_freqs, n_times)`. **See doc01 for the confirmed live `.npy` vs `.npz`
discrepancy** — the current corpus manifest finds only `.npz` on disk, but the loader globs only
`.npy`.

Repo-internal `outputs/` subtrees hold **derived** TFR-based products (aggregates, condition
maps — not the raw per-session arrays): `outputs/condition_tfr_maps_p1d1p2d2p3/` (+`_v2`/`_v3`),
`outputs/omission_aligned_tfr/`, `outputs/omission_tfr_maps{,_final,_ratio,_w1500}/`,
`outputs/stimulus_pooled_tfr_maps_w1500/`.

Scripts producing/precomputing TFR products: `precompute_tfr_arrays_v2.py` (primary pipeline
behind fig04's "now-accepted v3 corpus"; resolves area/probe/channel-slice via
`outputs/channel_area_vector/channel_area_vector.csv`, sidecar-free — supersedes
`precompute_tfr_arrays.py`, which depended on now-missing `D:/analysis/metadata/{stem}/
probe_areas.json` sidecars), `extract_condition_tfr_maps.py` (+`_v2`/`_v3`),
`extract_omission_tfr_maps.py`, `extract_stimulus_pooled_tfr_maps.py`,
`plot_omission_tfr_area_panels.py`, `run_tfr_precompute_all_sessions.sh`/
`run_tfr_precompute_batch.sh`.

## Spike-field coupling — status: retired, then revived (2026-08-15)

| Script | Status |
|---|---|
| `scripts/extract_spike_lfp_coupling.py` (v1) | **SUPERSEDED** — own docstring says so; depends on missing `probe_areas.json` sidecars. Its one existing output predates the sidecar gap (2026-07-30), preserved unedited (Conservation). |
| `scripts/extract_spike_lfp_coupling_v2.py` (2026-08-15) | **CURRENT extraction.** Identical PPC logic to v1; only change is sidecar-free area/probe resolution via `channel_area_vector.csv`. Output `outputs/spike_lfp_coupling/coupling_v2.npz`, kept separate from stale v1. Full-corpus: 22/22 sessions, 123,060 unit×band×context×area×layer results, 8,260 same-electrode exclusions (`EXCLUDE_RADIUS=2` channels — spike-waveform-leakage control), ~2h runtime; obs PPC range −0.034 to 0.483 (mean 0.005, consistent with near-zero-under-null). |
| `scripts/aggregate_spike_lfp_coupling_v2_corrected.py` | **CURRENT aggregation** — the corrected-design PPC rebuild Hamm explicitly requested 2026-08-15, reversing the `omission-signal` skill's default retirement stance. Splits cells by functional class (S+/S++/S−/S−−/O+/O++/O−/O−−) via `unit_master_features.csv`, in addition to area×layer×band×context. `Z_THRESH=1.96, ALPHA=0.05, MIN_SESSIONS=3`. Output `outputs/spike_lfp_coupling/class_hit_rates_v2.csv`. **Result: PROVISIONAL, non-null** — 37/520 class×context×band×area cells have a hit-rate 95% CI lower bound above alpha. 25/37 are beta band (14-30Hz); FEF (15/37) and PFC dominate. Contrast: the sliding-correlation PPC replacement (below) was fully null (0/11,700); cross-area imaginary coherency also fully null. |
| `scripts/extract_within_session_spk_lfp_sliding_corr.py` | The skill-named PPC-retirement replacement — trial-matched sliding-window correlation, unit's own spike-rate vs its own area's band-power trace. **Fully null (0/11,700)** — this is part of why Hamm asked for the PPC rebuild instead. |

**Bottom line**: PPC's status flipped mid-project. The `omission-signal` skill's default text
("PPC is retired") is now stale relative to the 2026-08-15 corrected rebuild's provisional
non-null result — flagged in doc09 as a skill-file update Hamm should approve (per `labyrinth`'s
Amendment rule, skill changes need explicit human approval, not an agent's unilateral edit).

## The corrected group-pooling design — canonical pattern, reused 3×

First implemented in `scripts/aggregate_within_session_lfp_lfp.py`; reused/adapted by
`aggregate_lfp_lfp_coupling_corrected.py` (imaginary coherency) and
`aggregate_spike_lfp_coupling_v2_corrected.py` (PPC v2). Three steps:

1. **Within-session z vs within-session shuffle null** (computed upstream by the extraction
   script). `z = (obs - null_mean) / null_std`, guarded against `null_std==0`. Channel pairs are
   collapsed to area pairs *within* each session first (a within-session summary, never a
   cross-session pool at this stage).
2. **Per-session binary significance decision**: a session counts as "significant" for a cell if
   `|z| >= Z_THRESH (1.96)`, same threshold across all reuses "for direct comparability."
3. **Pool across sessions as a proportion**, not a t-test on pooled point estimates: among
   sessions where the cell was actually recorded (partial coverage expected/fine), test hit-rate
   k/n against `ALPHA=0.05` via exact `jnwb.statistics.clopper_pearson(k, n, alpha)` (the
   canonical implementation — three duplicate implementations existed before consolidation).
   `above_chance = ci95_lo > ALPHA` — the CI **lower bound** must clear the nominal rate, not
   just the point estimate.

**Rationale** (explicit in the canonical script's docstring): "pooling happens after testing,
never before." This exact corpus produced 0/45–0/240 significant results **six separate times in
one week** when raw session point estimates were pooled and tested directly, despite huge
single-session effects — caused by large, opposite-signed between-animal variability in raw
point estimates, which pooling-before-testing treats as noise to average over, erasing the
effect before the group-level test ever sees it. Testing within-session first (immune to
between-animal scale differences) and pooling only the binary decisions avoids this. See
`omission-signal` skill §10 and `omission-statistics` skill for the same rule stated generally.

## Connectivity results — confirmed status as of 2026-08-17

| Method | Status | Result |
|---|---|---|
| Bivariate time-domain Granger, LFP-LFP (fig05) | **CONFIRMED NULL** (2026-08-04) | 0/150 survive Holm-Bonferroni across 3 families. Smallest p: low_gamma MT↔TEO delta, raw p=0.0077, p_holm=0.38 — "a candidate for follow-up, not a finding." 100% of session-level fits carry a diagnostic warning (expected for short, strongly-evoked, non-stationary LFP) — group-level test still valid, unit of inference is session-level point estimates. |
| Bivariate time-domain Granger, SPK-SPK (fig06) | **CONFIRMED NULL** (2026-08-04) | 0/45 survive Holm-Bonferroni. Smallest raw p: MT↔TEO net directionality (RXRR p=0.036/p_holm=0.32; RRRR p=0.050/p_holm=0.45) — same pair/direction as fig05's smallest edge, flagged "real cross-modality convergence worth follow-up," explicitly not reported as a finding. Third of three connectivity methods to fail on 2026-08-04. |
| Undirected LFP-LFP imaginary coherency | **NULL** (0/240) | Demoted from main figure to supplement. |
| Spectral (Geweke) Granger network (fig08) | **CONFIRMED** (as a manuscript figure artifact) | Distinct estimator (`granger_spectral`, frequency-resolved) from the null bivariate time-domain Granger above — **do not conflate fig05/fig06 (null) with fig08 (accepted)**; they test different things. |
| Spike-LFP PPC | **PROVISIONAL, non-null** (2026-08-15, reversing the skill default) | 37/520 cells, mostly beta-band, FEF/PFC-concentrated — see table above. |
| Transfer entropy | **Not confirmed either way** | Was running as a multi-hour background job for fig05 as of 2026-08-04; no dedicated TE status node found by this audit. Search for a post-2026-08-04 TE-specific evidence node before citing a TE result. |

Other `.lab` nodes worth distinguishing: `claim-oscillatory-coherence-08.json` is a higher-level
synthesis/hypothesis-linking node, not a direct report of this corpus's own coherence test —
its `status=CONFIRMED` refers to the node's own citation completeness, not a significant
empirical finding on this dataset; read closely before citing as a positive corpus result.

## Onset-latency / native-resolution TFR analyses — flagged for follow-up, not opened

Found by name but not deep-read this pass: `scripts/fit_lfp_band_onset_latency.py`,
`scripts/aggregate_omission_band_dampening_onset.py`,
`scripts/decode_omission_onset_sliding_window.py`, `scripts/aggregate_omission_onset_clusters.py`,
`scripts/diagnose_onset_hierarchy_boundary_pinning.py`,
`scripts/rehierarchy_test_clean_onsets_only.py`. Whether these operate at the TFR array's native
10ms resolution or a downsampled/binned one was not confirmed by this audit.
