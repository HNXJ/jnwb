# Downstream Agent Handout: Google Colab Visual Review Replication Notebook

This document provides operational context and implementation parameters for downstream agents running [reproduce_all_visual_reviews.ipynb](file:///d:/workspace/omission/notebooks/reproduce_all_visual_reviews.ipynb) in Google Colab connected to a local Jupyter runtime.

---

## 1. Local Jupyter Server Connection

To run this notebook in Google Colab with access to local drive files, the user must run the startup script [run_colab_jupyter.bat](file:///d:/workspace/omission/run_colab_jupyter.bat) on the local Windows workstation. This configures the local runtime:
- **Origin Authorization**: Allowed origin is set to `https://colab.research.google.com`.
- **Server Port**: Bound to port `8888` (override port retry option active).
- **Execution Target**:
  ```cmd
  jupyter notebook --ServerApp.allow_origin="https://colab.research.google.com" --ServerApp.port=8888 --ServerApp.port_retries=0 --no-browser
  ```
- **Connection Step**: In Google Colab, select the connection dropdown (top right) -> choose **"Connect to a local runtime"** -> enter `http://localhost:8888/` (and the token shown in the terminal stdout log if prompted).

---

## 2. Hard Data Dependencies (Local Storage Paths)

The notebook executes calculations on cached numpy arrays and raw NWB datasets located on the local machine. It maps these folders as follows:
- **`NWB_DIR`** (`D:/analysis/nwb`): Folder containing the raw `.nwb` session records.
- **`TFR_DIR`** (`D:/workspace/data/tfr_arrays`): Folder containing 720 pre-computed raw `.npy` trial time-frequency arrays (TFR arrays) used for band trace alignment.
- **`LAYER_MASKS_PATH`** (`D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json`): Layer crossover indices mapping probes to deep/superficial channels.
- **`DATABASE_CSV`** (`D:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv`): Master unit metadata sheet containing classifications (`sig_o_plus`, `sig_s_plus`, `sig_s_minus`).

---

## 3. Cell-by-Cell Pipeline Mechanics

### Cell 1: Environment Initialization
- Loads standard scientific dependencies (`pynwb`, `statsmodels.stats.multitest`, `scipy`).
- Defines canonical area array (`CANONICAL_AREAS` containing 11 visual/prefrontal regions).

### Cell 2: Omission-Aligned TFR Traces
- **Task**: Aligns and normalizes low/high-frequency LFP power relative to omission onset.
- **Logic**:
  - Discovers TFR array files matching condition codes.
  - Slices a relative time-window from $-1560$ ms to $+1040$ ms around omission onset.
  - Baseline normalizes relative power using pre-stimulus baseline values $[-500, 0]$ ms.
  - Balances trial count $N$ across Slots 2 & 3 per area-layer, averages band power, and exports 22 SVG trace diagrams to `outputs/publication_visual_review/aligned_omission_tfr_traces`.

### Cell 3: Family-Matched Raster Suites
- **Task**: Creates family-matched raster plots for Stable-Plus omission units.
- **Logic**:
  - Pulls the top omission-positive units from the database.
  - Filters trials by condition families (**A**: AXAB/AAXB; **B**: BXBA/BBXA; **R**: RXRR/RRXR).
  - Truncates to minimum trial count bounds for visual alignment, plotting spike rasters relative to omission onset.

### Cell 4: 22x22 LFP-LFP Spearman Matrices
- **Task**: Computes inter-area and inter-layer LFP-LFP Spearman correlation matrices.
- **Logic**:
  - Loads cached layer power traces from disk cache.
  - Calculates Spearman correlation $r$ and $p$-value for every possible pair of the 22 area-layers.
  - Applies **Benjamini-Hochberg False Discovery Rate (BH-FDR)** multiple test correction.
  - Outputs 7 correlation heatmaps (one per band) and saves stats table `tfr_all_pairs_correlation_stats.csv`.

### Cell 5: Time-Resolved Moving LFP-LFP Correlations
- **Task**: Plots sliding-window correlations over time between key inter-regional pathways.
- **Logic**:
  - Slides a 750 ms window in 50 ms steps across trial timecourses.
  - Computes sliding window Spearman $r$ values.
  - Runs **200 time-shuffles** on LFP signals to determine the 95th percentile shuffle threshold control limits.

### Cell 6: Spike-LFP Contrast Analysis Summary
- **Task**: Loads and validates completed spike-LFP moving-window correlation results.
- **Logic**:
  - Processes results from `spike_lfp_contrast_stats.csv`.
  - Performs Wilcoxon signed-rank comparison between omission (0–500 ms) and control epochs.
  - Displays top significant inter-area contrasts sorted by modulations.
