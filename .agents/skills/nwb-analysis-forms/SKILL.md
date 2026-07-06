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

## 4. Multi-Area Spectral Granger Causality
Computes directional lead-lag networks and connectivity routing between cortical areas.
```python
from jnwb.connectivity import granger_causality
# Returns directional connectivity matrix
gc_results = granger_causality(session, area1="V1", area2="PFC", frequency_band="beta")
```

## 5. Population Trajectory PCA (GPU-Accelerated)
Performs PCA trajectory analysis of population activity using PyTorch SVD.
```python
from jnwb.trajectory import compute_population_trajectory
# Computes trajectory dynamics in low-dimensional space
traj_results = compute_population_trajectory(session, area="PFC", n_components=3)
```

## 6. SVM Population Decoding
Trains linear SVM classifiers to predict trial type/omission identity.
```python
from jnwb.decoding import decode_trial_type
# Returns decoding accuracies and significance metrics
dec_results = decode_trial_type(session, area="PFC", time_window=(0.0, 2.0))
```