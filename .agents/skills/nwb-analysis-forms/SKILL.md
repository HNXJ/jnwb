---
name: nwb-analysis-forms
description: |
  Comprehensive NWB analysis forms and pipelines in the omission project.
  Includes single-unit rasters, multi-channel LFP power/TFR bands, layer-wise spectrolaminar motifs,
  directional spectral Granger networks, population trajectory PCA (SVD), and SVM population decoding.
---

# NWB Analysis Forms & Pipelines

## 1. Single-Unit Raster Suite
Generates aligned spike rasters, PSTH, and ACG for a neuron.
```python
import jnwb as oa
session = oa.read("D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb")
res = session.raster_suite(unit_id=2.0, condition=None, phase=2)
# Saves figures using Madelane Golden dark theme
res["figure"].savefig("outputs/task_01_raster.png", bbox_inches='tight')
```

## 2. 2D Log-Frequency TFR Spectrograms
Computes and plots baseline-normalized power spectrograms across theta, alpha, beta, and gamma bands.
```python
# Plots TFR power for a specific brain area and condition
session.plot_tfr(area="PFC", condition="AAXB", phase=3)
```

## 3. Layer-Wise Spectrolaminar Motifs
Identifies superficial and deep layer spectral power dynamics across visual hierarchies.
```python
# Computes layer-wise power (superficial vs deep)
session.spectrolaminar_motif(area="V4", condition="AAAB")
```

## 4. Bivariate Spectral Granger Causality
Computes directional lead-lag Granger causality between two continuous signals
(e.g. two LFP traces or two firing-rate time series) — takes raw arrays, not a
session/area pair. Returns residual diagnostics (Ljung-Box + ADF-like flag);
do not interpret GC as biological directionality when diagnostics warn.
```python
from jnwb.connectivity import granger_causality
# signal1, signal2 are 1D np.ndarray time series (same session/trial, two areas or two units)
gc_results = granger_causality(signal1, signal2, order="auto", device="cpu", criterion="aic")
# gc_results['F_2_to_1'], gc_results['F_1_to_2'], plus residual diagnostics
```

## 5. Population Trajectory PCA (GPU-Accelerated)
Performs PCA trajectory analysis of population activity using PyTorch SVD.
Requires an `epochs_df` (a DataFrame of trial onsets, e.g. from
`session.get_epochs(...)`) — GPU path uses PyTorch and needs
`torch.cuda.is_available()`; falls back to CPU otherwise.
```python
from jnwb.trajectory import compute_population_trajectory
epochs_df = session.get_epochs(condition="AAAB", phase=2, correct_only=True)
traj_results = compute_population_trajectory(
    session, area="PFC", epochs_df=epochs_df,
    time_window_ms=(-1000.0, 2000.0), bin_size_ms=20.0, n_components=3,
)
# traj_results['trajectory'], ['explained_variance'], ['unit_ids'], ['bin_centers']
```

## 6. SVM Population Decoding
Trains linear SVM classifiers (nested CV) to predict stimulus identity or
omission presence from population activity. Returns `accuracy`, `f1`, `auc`,
and `majority_baseline_accuracy` (compare `accuracy` against the baseline to
check the classifier beats chance/class-imbalance, not just tracks it).
```python
from jnwb.decoding import decode_stimulus_identity, decode_omission_presence
# Two conditions, e.g. AAAB vs BBBA
dec_results = decode_stimulus_identity(session, area="PFC", condition_pairs=("AAAB", "BBBA"))
# Or specifically standard-vs-omission (thin wrapper around decode_stimulus_identity)
om_results = decode_omission_presence(session, area="PFC", standard_condition="AAAB", omission_condition="AAXB")
```