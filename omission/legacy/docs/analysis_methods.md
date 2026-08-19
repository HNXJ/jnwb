# Omission Analysis Methods

This document details the spiking metrics, spectral analyses, decoding frameworks, and statistical methods used to quantify predictable and surprise neural dynamics.

---

## 1. Single-Unit Spiking Dynamics

### PSTH and Baselines
- **Binned PSTH**: `jnwb.functions.psth_analysis` computes the canonical PSTH as raw binned spike counts (`bin_size_ms`, default 10 ms), not Gaussian-kernel-smoothed. Gaussian smoothing (`scipy.ndimage.gaussian_filter1d`, various `sigma` values depending on plot type) is applied separately in specific `jnwb.viz` trace visualizations, not universally at PSTH-generation time.
- **Reference Point**: All trials are aligned to Code `101.0` (Presentation 1 Onset) or Phase 2 Onsets.
- **Baseline Window**: Baseline firing rate is calculated over the $[-1000, 0]\text{ ms}$ pre-stimulus window.

### Fano Factor Quenching
- **Objective**: Quantify the reduction in across-trial spike variability.
- **Mean-Matched Fano Factor (MMFF)**: Implemented using the Churchland (2010) method. Matches firing rate distributions across time bins to decouple variance changes from changes in mean rate.

### Refractory Period & Waveform Classification
- **Refractory Violations**: `jnwb.analyzers.UnitAnalyzer` tests significance via a Poisson survival-function comparison of observed refractory-window spike count against the baseline ACG rate (not a raw violation-percentage cutoff); a unit is flagged `is_single_unit` when this test's p-value is $< 0.05$.
- **Trough-to-Peak Duration**: `waveform_duration_us` is extracted and carried through unit metadata (`jnwb.metadata`, `jnwb.analyzers.UnitAnalyzer.quality_metrics`), but interneuron/pyramidal classification by a $350/450\ \mu\text{s}$ cutoff is not currently implemented as a jnwb function - treat this as a manual/offline convention, not an automated jnwb classification, until such a function exists.

---

## 2. Spectral Analysis (LFP & TFR)

### Time-Frequency Representation (TFR)
- **Multitaper Spectrogram**: Computed using STFT or multitaper methods.
- **Resolution**: 100ms Hanning window, 98% overlap (2ms steps) for high-fidelity onset detection.
- **Frequency Bands**: Theta ($4\text{–}8\text{ Hz}$), Alpha ($8\text{–}12\text{ Hz}$), Beta ($12\text{–}30\text{ Hz}$), Gamma ($30\text{–}80\text{ Hz}$).
- **Relative Power Change (dB)**:
  \[
  \text{Power}_{\text{dB}} = 10 \times \log_{10}\left(\frac{P_{\text{time}}}{P_{\text{baseline}}}\right)
  \]
  Baseline is computed using the average power per frequency during pre-stimulus or delay periods.

### Spectrolaminar laminar Mapping
- **Superficial vs. Deep**: Resolved using putatively assigned channel depth metrics or Current Source Density (CSD).
- **vFLIP2 mapping**: Identifies the reversal layer separating superficial feedback/output layers from deep feedback layers.

---

## 3. Population Decoding & Representations

### SVM Information Decoding
- **Classifier**: Linear Support Vector Machine (SVM).
- **Target 1 (Identity)**: A vs. B stimulus classification during sequence presentation.
- **Target 2 (Omission)**: Standard vs. Omitted (e.g., AAAX vs. AAAB) trial classification during the omission window.
- **Cross-Validation**: 5-fold cross-validation with stratified trial splits.

### Representational Similarity Analysis (RSA) & CKA
- **RSA**: Calculates Representational Dissimilarity Matrices (RDMs) using Pearson distance ($1 - r$) across neural population activity vectors.
- **Centered Kernel Alignment (CKA)**: Quantifies representational similarity between layers or recording areas directly, accounting for orthogonal rotations.

---

## 4. Directional Connectivity & Mutual Information

### Mutual Information (MI)
- Vectorized computation of mutual information between spike trains and between LFP bands across inter-area pairs.
- Delay/Lag estimation: Identifies the time offset (lag) at which inter-area mutual information peaks.
