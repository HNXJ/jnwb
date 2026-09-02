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
   - `fit_exponential_onset` returns `"bound_status"` which is `"lower" | "upper" | None`.
   - `None` indicates an interior, unconstrained fit.
   - `"lower"` or `"upper"` indicates the optimizer is constrained against outer boundary bounds (censoring). Never treat a boundary-constrained fit as an unconstrained physiological latency.

3. **Causal Smoothing & Group Latency Delay**:
   - `causal_exp_smooth(rate, bin_ms, tau_ms)` performs a forward-only finite exponential-kernel convolution ($5\tau$) with left-zero padding.
   - It avoids future-leakage acausal filtering, but introduces an intrinsic group delay ($\bar{t} \approx \tau_{\text{ms}}$, $t_{50\%} \approx 0.693\,\tau_{\text{ms}}$). Downstream latency windows must account for this shift.

4. **Independent RNG Injection**:
   - Resampling and permutation primitives (`StatisticalAnalysis.bootstrap_ci`, `permute_labels`, `paired_fire_prob_test`, `granger`) require an explicit `rng=np.random.default_rng(seed)` or `seed` argument.
   - Never mutate global NumPy/Python random seeds. Never use salted hashes (`hash(...)`) across process boundaries.

5. **Permutation Exchangeability**:
   - In hierarchical or blocked experimental designs (e.g. trials within sessions/blocks), use `permute_labels(y, scheme="within_group", groups=...)`.
   - Global permutation (`scheme="global"`) assumes complete exchangeability across all units and violates trial-block independence when temporal/session clusters exist.

6. **Artifact Detection Precedes Repair**:
   - `repair_lfp_trials` computes a robust cross-channel synchrony statistic ($z > 6.0$) and substitutes flagged cells with the **cross-trial median**.
   - Inspect `frac_flagged` and diagnostic returns. If raw spike waveforms or high-precision temporal alignment are analyzed, evaluate whether median-substituted LFP is appropriate.

7. **Estimand & Causal Hierarchy**:
   - $\text{Association} \ne \text{Directionality} \ne \text{Causality}$.
   - Pearson/Spearman correlation measures linear/monotonic association.
   - `granger` and `phase_slope_index` measure temporal-lag asymmetry (predictive directionality), not anatomical/physical causality. Never use causal verbs for observational lag asymmetries.

8. **Dataset-Agnostic Boundary**:
   - `jnwb` is strictly generic. Experiment-specific condition codes, event names, trial tables, and corpus file structures belong in the user's project scripts/skills, never in `jnwb`.

---

## 2. Operational Task-to-Primitive Routing Matrix

| Scientific Task | Recommended `jnwb` Primitive | Required Inputs & Coordinates | Key Assumptions & Pitfalls | Output Object / Keys | Canonical Documentation |
|---|---|---|---|---|---|
| **Single-Trial Complex Time-Frequency** | `jnwb.complex_tfr` | Signal $(C, T)$ or $(T,)$, `fs` (Hz), `freqs` (Hz array), `n_cycles` | $L_1$ amplitude normalization yields unit cosine amplitude = 1.0; check `coi_mask` for boundary distortion | `ComplexTFR` dataclass (`z`, `power`, `phase`, `amplitude`, `coi_mask`) | [`docs/04_spectral_analysis_and_tfr.md`](docs/04_spectral_analysis_and_tfr.md) |
| **Streaming / Multi-Trial TFR Accumulation** | `jnwb.TFRAccumulator` | `shape=(C, F, T)`, incoming trial `z` and `coi_mask` | Numerically stable Welford running variance; avoids storing full $N \times C \times F \times T$ tensors in RAM | `acc.power()`, `acc.itc()`, `acc.evoked()`, `acc.induced()` | [`docs/04_spectral_analysis_and_tfr.md`](docs/04_spectral_analysis_and_tfr.md) |
| **PSTH & Firing Rate Dynamics** | `jnwb.raster_psth` | `st` (spike times), `onsets` (event times), `win_ms`, `bin_ms` | Requires seconds for times, ms for window/bin; returns firing rate in Hz | `(time_bins_ms, mean_rate_hz, sem_rate_hz)` tuple | [`docs/06_spikes_psth_and_onset_dynamics.md`](docs/06_spikes_psth_and_onset_dynamics.md) |
| **Causal Spike Rate Smoothing** | `jnwb.causal_exp_smooth` | `rate` (1D binned array), `bin_ms`, `tau_ms` | Forward-only finite exponential kernel ($5\tau$); introduces latency delay $\sim \tau$; no future leakage | `smoothed_rate` (1D np.ndarray) | [`docs/06_spikes_psth_and_onset_dynamics.md`](docs/06_spikes_psth_and_onset_dynamics.md) |
| **Physiological Latency Fitting** | `jnwb.fit_exponential_onset` | `t_ms`, `rate`, `t0_bounds=(t_min, t_max)` | Check `fit["bound_status"] is None` (interior) vs `"lower"` / `"upper"` (censored) | Dict with `t0`, `tau`, `amplitude`, `baseline`, `r2`, `bound_status` | [`docs/06_spikes_psth_and_onset_dynamics.md`](docs/06_spikes_psth_and_onset_dynamics.md) |
| **Bootstrap Confidence Intervals** | `jnwb.StatisticalAnalysis.bootstrap_ci` | `data` (1D/2D array), `n_bootstrap`, `rng` | Assumes i.i.d. observations along bootstrap axis; pass explicit `Generator` | Dict with `bootstrap_ci`, `mean`, `sem` | [`docs/07_statistical_inference_and_nulls.md`](docs/07_statistical_inference_and_nulls.md) |
| **Condition Permutation Testing** | `jnwb.permute_labels` | `y` (labels), `scheme="global"|"within_group"`, `groups`, `rng` | Preserve block/session exchangeability with `within_group` | Permuted `y` array | [`docs/07_statistical_inference_and_nulls.md`](docs/07_statistical_inference_and_nulls.md) |
| **Directed Lag Coupling** | `jnwb.granger` | 1D time series `X`, `Y`, `order`, `n_surrogates`, `seed` | Measures predictive variance reduction; test with time-shift surrogates | `DirectedResult` (`metric`, `p_value`, `surrogates`) | [`docs/08_directed_connectivity_and_information.md`](docs/08_directed_connectivity_and_information.md) |
| **Cross-Area Phase Slope** | `jnwb.phase_slope_index` | `X`, `Y`, `fs`, `bands` | Non-zero slope of cross-spectral phase indicates driver/receiver lag | `DirectedResult` (`metric`, `std_error`, `p_value`) | [`docs/08_directed_connectivity_and_information.md`](docs/08_directed_connectivity_and_information.md) |
| **Linear SVM Decoding** | `jnwb.nested_cv_linear_svm` | `X` $(N, D)$, `labels` $(N,)$, `n_splits` | Outer CV evaluates generalization; inner CV tunes regularization $C$ | Dict with `accuracy`, `confusion_matrix`, `majority_baseline` | [`docs/09_decoding_and_visual_qc.md`](docs/09_decoding_and_visual_qc.md) |
| **Multichannel Bad Channel QC** | `jnwb.bad_channels_from_correlation` | `corr_matrix` from `jnwb.channel_correlation_matrix` | Detects disconnected or saturated probe channels | Boolean mask $(C,)$ of bad channels | [`docs/05_artifact_detection_and_repair.md`](docs/05_artifact_detection_and_repair.md) |
| **LFP Outlier Trial Repair** | `jnwb.repair_lfp_trials` | `segments` $(N_{\text{trials}}, C, T)$, `times_ms`, `z_thresh=6.0` | Cross-channel synchrony detection + cross-trial median substitution | `(repaired_segments, frac_flagged, diagnostics)` tuple | [`docs/05_artifact_detection_and_repair.md`](docs/05_artifact_detection_and_repair.md) |
| **Channel-to-Brain Area Mapping** | `jnwb.map_peak_channel_to_area` | `peak_channel_id`, `electrodes_df` | Works with comma/slash separated multi-area strings without external project imports | Standardized anatomical area string or `None` | [`docs/02_paths_addressing_metadata.md`](docs/02_paths_addressing_metadata.md) |

---

## 3. Minimal Composition Recipes

### Recipe A: Time-Frequency Streaming Pipeline
```python
import jnwb
import numpy as np

# 1. Define physical coordinates
fs = 1000.0  # Hz
freqs = np.linspace(10.0, 60.0, 11)  # 10 to 60 Hz
n_channels, n_times = 4, 500

# 2. Initialize accumulator
acc = jnwb.TFRAccumulator(shape=(n_channels, len(freqs), n_times))

# 3. Stream trials
rng = np.random.default_rng(42)
for _ in range(5):
    trial_signal = rng.normal(size=(n_channels, n_times))
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
rng = np.random.default_rng(42)
spikes = np.sort(rng.uniform(0.0, 10.0, 100))
events = np.array([1.0, 3.0, 5.0, 7.0])

time_bins, rate_hz, sem_hz = jnwb.raster_psth(
    st=spikes,
    onsets=events,
    win_ms=(-100.0, 400.0),
    bin_ms=10.0
)

# 2. Causal smoothing (finite exponential kernel)
smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)

# 3. Fit onset latency with boundary check
fit = jnwb.fit_exponential_onset(
    t_ms=time_bins,
    rate=smooth_hz,
    t0_bounds=(0.0, 200.0)
)

if fit["bound_status"] is None:
    print(f"Verified onset latency: {fit['t0']:.1f} ms (R2 = {fit['r2']:.2f})")
else:
    print(f"Latency constrained against boundary ({fit['bound_status']}); censored.")
```

### Recipe C: LFP Artifact Detection & Median Repair
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
lfp_trials = rng.normal(size=(10, 4, 300))  # (n_trials, n_channels, n_times)

# Inject an artifact on trial 0
lfp_trials[0, :, 100:120] += 50.0

repaired, frac_flagged, diag = jnwb.repair_lfp_trials(
    segments=lfp_trials,
    z_thresh=6.0
)
print(f"Repaired fraction: {frac_flagged:.3f}, flagged cells: {diag['n_flagged_cells']}")
```
