# Analysis Pipelines Specifications

Below is the list of analysis pipeline scripts to be maintained under `scripts/`.
Each script follows the naming convention `suite_01_<short_name>.py` (or matching indices) and receives inputs specifying the target dataset subset (e.g., session, area, condition) and saves the fully vectorized `.svg` figure formatted as `<script_name>_yymmdd.svg` (or matching specific execution dates).
All figures involving trial-level averages, convolved arrays, channel comparisons, or spectral time-series include proper statistical tests (parametric/non-parametric ANOVA, t-tests for difference from 0, or permutation-shuffled bounds).

---

## List of Analysis Pipeline Scripts

### 1. `suite_01_raster_s_om.py` (Raster suite of S+/S-/O+ neurons)
- **Visualization**: $4 \times 3$ subplots of four exemplars (e.g. S+, S-, O+, Null/Other).
- **Subplots**: Each neuron has three subplot columns corresponding to condition groups (Standard, Deviant/Omission, and Control/Shuffle sequences).
- **Data**: Spikes convolved with Gaussian kernel (e.g., $15\text{ ms}$ width) to render smooth PSTHs alongside raw raster marks.
- **Statistics**: Annotation showing firing rate difference between presentation and baseline epochs using paired t-tests or Wilcoxon signed-rank tests.

### 2. `suite_02_raster_s2_om2.py` (Raster suite of S++/S--/O++ neurons)
- **Visualization**: $4 \times 3$ subplots of four exemplars exhibiting strong double-sequence response phenotypes (S++, S--, O++).
- **Subplots**: Columns mapped across Standard, Deviant, and Control conditions.
- **Data**: Units selected based on template-matching/correlation across multi-sequence cycles.
- **Statistics**: Non-parametric Friedman test or repeated-measures ANOVA checking response consistency across consecutive trial cycles.

### 3. `suite_03_tfr_heatmap.py` (TFR Spectrogram Heatmap)
- **Visualization**: 2D spectrogram power heatmap (Freq vs. Time) for a selected area (out of the 11 canonical areas) for one specified condition group (out of 12 behavioral sequences).
- **Baseline**: dB normalized against pre-stimulus baseline interval $[-500, 0]\text{ ms}$ relative to $p1$ onset.
- **Statistics**: Grid of pixel-wise permutation significance tests (FDR-corrected) showing bins significantly deviating from baseline.

### 4. `suite_04_tfr_band_traces.py` (Trace-TFR 1D traces)
- **Visualization**: 1D time-series power trace with $\pm$SEM shaded regions for 5 standard frequency bands (e.g., Theta, Beta, Gamma, High-Gamma, Ultra-High-Gamma) for a selected condition group.
- **Data**: Extracted from average power across stable-plus channels of a target area.
- **Statistics**: Running t-test against baseline ($0$) for each band, with FDR-corrected significance markers plotted along the time axis.

### 5. `suite_05_pie_composition.py` (Pie charts of sequence responsive units)
- **Visualization**: Pie charts depicting the composition percentage of S+, S-, O+, and Null populations.
- **Classification**: Units classified based on strict detrended template correlations using permutation-shuffled bounds ($5000$ shuffles, $p < 0.05$).
- **Statistics**: Chi-square goodness-of-fit test comparing observed proportions against null distributions or baseline session expectations.

### 6. `suite_06_spike_lfp_coherence.py` (Spike-LFP Relationship)
- **Visualization**: Coherence or Phase-Locking Index (PLI) curves for S+, S-, and O+ units relative to local LFP channels.
- **Statistics**: Rayleigh test for circular uniformity to determine phase-locking significance, or jackknife coherence confidence intervals.

### 7. `suite_07_rsa_spk_lfp.py` (RSA of Spiking to LFP)
- **Visualization**: Representational Similarity Analysis matrices comparing spiking population trajectories and TFR power matrices.
- **Statistics**: Mantel test or permutation tests to assess similarity matrix correlations across modalities and conditions.
