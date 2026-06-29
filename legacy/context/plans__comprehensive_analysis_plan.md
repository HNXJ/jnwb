# Comprehensive Omission Analysis & Figure Generation Plan

## 1. Core Data Matrix & Unit Filtering (`src/core/data_loader.py`)
All downstream analyses depend on a strictly validated 12 (conditions) $\times$ 9 (time windows) signal matrix.

**Time Windows (9):**
`[fx(-500:0), p1(0:531), d1(531:1031), p2(1031:1562), d2(1562:2062), p3(2062:2593), d3(2593:3093), p4(3093:3624), d4(3624:4124)]`

**Condition Groups (12):**
`AAAB`, `BBBA`, `RRRR`, `AXAB`, `BXBA`, `RXRR`, `AAXB`, `BBXA`, `RRXR`, `AAAX`, `BBBX`, `RRRX`

**Unit Inclusion Criteria (SPK):**
Implemented in `src/analysis/signal.py` under `mode="spk"`:
- Presence Ratio > 0.95 across all trials.
- Mean Firing Rate > 1.0 Hz.
- Absolute Zero-Tolerance: Exclude any unit exhibiting exactly 0 Hz firing across any entire trial.

## 2. Functional Unit Classification (`src/analysis/stats.py`)
Extracting the 12x9 firing rate matrix allows deterministic classification of single units.

**Classification Logic:**
- **S+ (Stimulus Driven):** $FR(p_1) > FR(fx)$
- **S- (Stimulus Suppressed):** $FR(fx) > FR(p_1)$
- **O+ (Omission Driven):** Focused on the pure prediction error windows:
  - 2nd Omission: $FR(\text{AXAB}, p_2) > FR(\text{AXAB}, d_1)$
  - 3rd Omission: $FR(\text{AAXB}, p_3) > FR(\text{AAXB}, d_2)$
  - 4th Omission: $FR(\text{AAAX}, p_4) > FR(\text{AAAX}, d_3)$

## 3. Spectral & LFP Methodologies (`src/analysis/signal.py`)
Following the spectral methods outlined in Nitzan 2025, van Kerkoerle 2014, and Mendoza-Halliday 2024:
- **TFR Computation**: Compute STFT/wavelet spectrograms on omission-local windows. Keep trial structure until *after* normalization.
- **Normalization**: Baseline normalize to the late pre-omission delay window to isolate the predictive component. Calculate dB change.
- **Band-Specific Collapse**: Extract canonical bands: $\theta$ (Theta), $\alpha$ (Alpha), $\beta$ (Beta), $\gamma_1$ (low Gamma), and $\gamma_2$ (high Gamma).
- **Spectrolaminar Anchoring**: Use the FLIP/vFLIP method (Mendoza-Halliday) to identify layers (Gamma peaks superficially; alpha-beta peaks deeply). Compute Current Source Density (CSD) to confirm true omission sink/source signatures.

## 4. Eight-Figure Manuscript Execution Plan (`src/main.py`)

### Figure 1: Theory Schematic
- **Content:** Predictive routing / signal-noise routing models (L2/3 vs. L5/6), emphasizing the omission window as the key test of internally driven prediction errors.

### Figure 2: Experimental Design & Recording Summary
- **Content:** Brain/area layout, 128-channel laminar probe configuration, CSD map demonstrating layer assignments. Task timeline showing A-B-R vs. X-fx-d and the specific omission families.

### Figure 3: Single-Unit Responses
- **Pipeline:** `mode="spk"`
- **Content:** Rasters and PSTHs for S+, S-, and O+ neurons. Include linear/sigmoidal fits on omission responses to classify ramp-like vs. step-like area dynamics.

### Figure 4: Population State-Space Dynamics & Clusters
- **Pipeline:** `compute_statistics(data, stat_type="manifold")`
- **Content:** 3D PCA trajectories comparing stimulus vs. omission paths. Use cluster heatmaps (k-means) validated via CNN to show state divergence, confirming the omission state is an active, non-zero representational state.

### Figure 5: Time-Frequency Spectrograms (TFR)
- **Pipeline:** `mode="lfp"`
- **Content:** Omission-centered heatmaps showing baseline-normalized dB power change. Compare Stim vs. Omission directly to see which frequency bands (e.g., high-gamma bursts vs. alpha/beta shifts) carry the omission signal.

### Figure 6: Band-Specific LFP Dynamics
- **Pipeline:** `mode="lfp"`
- **Content:** Traces broken down by canonical frequency bands ($\theta, \alpha, \beta, \gamma_1, \gamma_2$). Layer-resolved profiles demonstrating feedforward vs. feedback oscillation routing during the predictive period.

### Figure 7: Spike-Field Coupling (SFC)
- **Pipeline:** `compute_statistics(data, stat_type="sfc")`
- **Content:** Pairwise Phase Consistency (PPC) and phase-of-firing polar plots. **CRITICAL:** Use matched-spike/PPC methods to rigorously correct for the sparse firing of omission neurons. Prove whether "Omission Neurons" tightly phase-lock to specific LFP rhythms (e.g., beta/theta) while non-relevant neurons are suppressed.

### Figure 8: Cross-Area Coordination
- **Pipeline:** `compute_statistics(data, stat_type="connectivity")`
- **Content:** Ridge regression on residual activity (subtracting PSTH) and Canonical Correlation Analysis (CCA) to map area-to-area interaction during omissions. Granger causality directionality plots and RSA/CKA maps to show how the whole hierarchy coordinates the prediction error.