---
name: jnwb
description: Operational decision routing and neuroscientific safeguards for using the generic jnwb electrophysiology and statistical analysis library.
---

# `jnwb` — Operational Routing & Scientific Safeguards

This skill guides AI agents and researchers in selecting, composing, and safely executing `jnwb` primitives for high-density electrophysiology, time-frequency analysis, and statistical neuroscience.

---

## 1. Golden Invariants & Epistemic Safeguards

Before selecting or executing any `jnwb` operation, enforce these 8 non-negotiable scientific invariants:

1. **Physical Frequency Coordinates**:
   - `complex_tfr` and spectral functions require an explicit, physical frequency array `freqs` in Hertz (e.g. `np.linspace(10, 60, 11)`).
   - Never assume index spacing equals Hz. Always pass `fs` (sampling frequency in Hz).

2. **Onset Censoring & `bound_status`**:
   - `fit_exponential_onset` returns `bound_status ∈ {"interior", "lower_bound", "upper_bound"}`.
   - Fits on boundary constraints (`bound_status != "interior"`) indicate censoring or unidentifiable onset. Never treat a censored boundary fit as a verified physiological latency.

3. **Causal Smoothing & Group Latency Delay**:
   - `causal_exp_smooth(x, bin_ms, tau_ms)` avoids future-leakage acausal filtering, but introduces a causal group delay proportional to $\tau$.
   - Latency windows downstream must explicitly account for $\tau$ or use onset estimators that model baseline pre-transition dynamics.

4. **Independent RNG Injection**:
   - Statistical estimators (`bootstrap_ci`, `permute_labels`, `exploratory_compare`, `granger`) require an explicit `rng=np.random.default_rng(seed)` or `seed` argument.
   - Never mutate global NumPy/Python random seeds. Never use salted hashes (`hash(...)`) across process boundaries.

5. **Permutation Exchangeability**:
   - In hierarchical or blocked experimental designs (e.g. trials within sessions/blocks), use `permute_labels(..., scheme="within_group", group_ids=...)`.
   - Global permutation (`scheme="global"`) assumes complete exchangeability across all units and violates trial-block independence when temporal/session clusters exist.

6. **Artifact Detection Precedes Repair**:
   - `repair_lfp_trials` uses cross-channel linear interpolation.
   - If raw spike waveforms or high-precision temporal alignment are analyzed, interpolate with caution. Always inspect `frac_repaired` from diagnostic returns.

7. **Estimand & Causal Hierarchy**:
   - $\text{Association} \ne \text{Directionality} \ne \text{Causality}$.
   - Pearson/Spearman correlation measures linear/monotonic association.
   - `granger` and `phase_slope_index` measure temporal-lag asymmetry (predictive directionality), not anatomical/physical causality. Never use causal verbs for observational lag asymmetries.

8. **Dataset-Agnostic Boundary**:
   - `jnwb` is strictly generic. Experiment-specific condition codes, event names, trial tables, and corpus file structures belong in the user's project scripts/skills, never in `jnwb`.

---

## 2. Operational Task-to-Primitive Routing Matrix

| Scientific Task | Recommended `jnwb` Primitive | Required Inputs & Coordinates | Key Assumptions & Pitfalls | Output | Canonical Documentation |
|---|---|---|---|---|---|
| **Single-Trial Complex Time-Frequency** | `complex_tfr` | Signal $(C, T)$ or $(T,)$, `fs` (Hz), `freqs` (Hz array), `n_cycles` | $L_1$ amplitude normalization yields unit cosine amplitude = 1.0; check `coi_mask` for boundary distortion | `ComplexTFR` dataclass (`z`, `power`, `phase`, `coi_mask`) | [`docs/04_spectral_analysis_and_tfr.md`](docs/04_spectral_analysis_and_tfr.md) |
| **Streaming / Multi-Trial TFR Accumulation** | `TFRAccumulator` | `shape=(C, F, T)`, incoming trial `z` and `coi_mask` | Numerically stable Welford running variance; avoids storing full $N \times C \times F \times T$ tensors in RAM | `acc.power()`, `acc.itc()`, `acc.evoked()`, `acc.induced()` | [`docs/04_spectral_analysis_and_tfr.md`](docs/04_spectral_analysis_and_tfr.md) |
| **PSTH & Firing Rate Dynamics** | `raster_psth` | `spike_times` (1D sec), `event_onsets` (1D sec), `win_ms`, `bin_ms` | Requires sorted spike times; returns spike counts normalized to Hz | `time_bins`, `mean_rate_hz`, `sem_rate_hz` | [`docs/06_spikes_psth_and_onset_dynamics.md`](docs/06_spikes_psth_and_onset_dynamics.md) |
| **Causal Spike Rate Smoothing** | `causal_exp_smooth` | `signal` (1D array), `bin_ms`, `tau_ms` | Single-pole IIR filter; introduces latency shift $\sim \tau$; no future data leakage | `smoothed_signal` (same length) | [`docs/06_spikes_psth_and_onset_dynamics.md`](docs/06_spikes_psth_and_onset_dynamics.md) |
| **Physiological Latency Fitting** | `fit_exponential_onset` | `time_bins`, `psth`, `t0_bounds=(t_min, t_max)` | Check `fit["bound_status"]`; boundary fits indicate censoring | Dict with `t0`, `tau`, `amp`, `bound_status`, `r2` | [`docs/06_spikes_psth_and_onset_dynamics.md`](docs/06_spikes_psth_and_onset_dynamics.md) |
| **Bootstrap Confidence Intervals** | `StatisticalAnalysis.bootstrap_ci` | `data` (1D/2D array), `n_bootstrap`, `rng` | Assumes i.i.d. observations along bootstrap axis; pass explicit `Generator` | Dict with `bootstrap_ci`, `mean`, `sem` | [`docs/07_statistical_inference_and_nulls.md`](docs/07_statistical_inference_and_nulls.md) |
| **Condition Permutation Testing** | `permute_labels` | `labels`, `scheme="global"|"within_group"`, `group_ids`, `rng` | Preserve block/session exchangeability with `within_group` | Permuted `labels` array | [`docs/07_statistical_inference_and_nulls.md`](docs/07_statistical_inference_and_nulls.md) |
| **Exploratory Dual Comparison** | `exploratory_compare` | `group_a`, `group_b`, `rng` | Reports both Welch $t$-test and Mann-Whitney $U$ alongside bootstrap $\Delta$ | Dict with test statistics, $p$-values, effect sizes | [`docs/07_statistical_inference_and_nulls.md`](docs/07_statistical_inference_and_nulls.md) |
| **Multiple Testing Correction** | `fdr_correct` / `bonferroni_correct` | `p_values` array, `alpha=0.05` | Benjamini-Hochberg assumes positive dependence (PRDS); Bonferroni controls FWER | Boolean rejection mask and adjusted $p$-values | [`docs/07_statistical_inference_and_nulls.md`](docs/07_statistical_inference_and_nulls.md) |
| **Directed Lag Coupling** | `granger` | 1D time series `X`, `Y`, `order`, `n_surrogates`, `seed` | Measures predictive variance reduction; test with time-shift surrogates | `DirectedResult` (`metric`, `p_value`, `surrogates`) | [`docs/08_directed_connectivity_and_information.md`](docs/08_directed_connectivity_and_information.md) |
| **Cross-Area Phase Coupling** | `phase_slope_index` | `X`, `Y`, `fs`, `freq_range` | Non-zero slope of cross-spectral phase indicates driver/receiver lag | Normalized PSI value and standard error | [`docs/08_directed_connectivity_and_information.md`](docs/08_directed_connectivity_and_information.md) |
| **Linear SVM Decoding** | `nested_cv_linear_svm` | `X` $(N, D)$, `y` $(N,)$, `n_splits`, `c_values`, `random_state` | Outer CV evaluates generalization; inner CV tunes regularization $C$ | Dict with `accuracy`, `confusion_matrix`, `best_c` | [`docs/09_decoding_and_visual_qc.md`](docs/09_decoding_and_visual_qc.md) |
| **Multichannel Bad Channel QC** | `detect_flat_or_noisy_channels` | Multichannel array $(C, T)$, correlation and variance thresholds | Detects disconnected or saturated probe channels | Boolean mask $(C,)$ of bad channels | [`docs/05_artifact_detection_and_repair.md`](docs/05_artifact_detection_and_repair.md) |
| **LFP Outlier Trial Repair** | `repair_lfp_trials` | `lfp_trials` $(C, \text{trials}, T)$, `threshold_sd` | Replaces extreme voltage outliers by linear interpolation across neighboring channels | Repaired LFP array, `frac_repaired`, diagnostic log | [`docs/05_artifact_detection_and_repair.md`](docs/05_artifact_detection_and_repair.md) |
| **Channel-to-Brain Area Mapping** | `map_peak_channel_to_area` | `peak_channel_id`, `electrodes_df` | Works with comma/slash separated multi-area strings without external project imports | Standardized anatomical area string | [`docs/02_paths_addressing_metadata.md`](docs/02_paths_addressing_metadata.md) |

---

## 3. Minimal Composition Recipes

### Recipe A: Time-Frequency Streaming Pipeline
```python
import jnwb
import numpy as np

# 1. Define physical coordinates
fs = 1000.0  # Hz
freqs = np.linspace(10.0, 60.0, 11)  # 10 to 60 Hz
n_channels, n_times = 8, 1000

# 2. Initialize accumulator
acc = jnwb.TFRAccumulator(shape=(n_channels, len(freqs), n_times))

# 3. Stream trials
for trial_signal in trial_generator:
    tfr = jnwb.complex_tfr(trial_signal, fs=fs, freqs=freqs, n_cycles=5.0)
    acc.add_trial(tfr.z, valid=tfr.coi_mask)

# 4. Extract power and phase-locking
mean_power = acc.power()  # (n_channels, n_freqs, n_times)
itc = acc.itc()           # Inter-Trial Coherence in [0, 1]
```

### Recipe B: Spike PSTH & Latency Estimation Pipeline
```python
import jnwb
import numpy as np

# 1. Compute PSTH
time_bins, rate_hz, sem_hz = jnwb.raster_psth(
    spike_times=spikes,
    event_onsets=events,
    win_ms=(-100.0, 400.0),
    bin_ms=10.0
)

# 2. Causal smoothing
smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)

# 3. Fit onset latency with boundary check
fit = jnwb.fit_exponential_onset(
    time_bins=time_bins,
    psth=smooth_hz,
    t0_bounds=(0.0, 200.0)
)

if fit["bound_status"] == "interior":
    print(f"Verified onset latency: {fit['t0']:.1f} ms (R2 = {fit['r2']:.2f})")
else:
    print(f"Latency censored ({fit['bound_status']}); not identifiable.")
```
