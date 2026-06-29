# Omission Operations & Troubleshooting

This document outlines common pipeline troubleshooting steps, anatomical mapping rules, and the 15-Step LFP-NWB Analysis pipeline standards.

---

## 1. Troubleshooting & Debugging

### The "Zero Neuron" & Missing Area Bug
- **Symptoms**: Areas like `V3d`, `TEO`, or `FST` show zero units or are missing from plots.
- **Root Cause**: Reliance on hardcoded or incomplete metadata registries; failure to parse multi-area descriptors (e.g. `V1, V2` labels).
- **Anatomical Mapping Rules**:
  1. **Probe Identification**: Probe ID is determined by `peak_channel_id // 128`.
  2. **Multi-Area Segment Split**: Divide the 128 channels of a probe into equal segments matching the area labels.
  3. **V3 Special Case**: Split channels assigned to `V3` 50/50 between `V3d` (superficial/dorsal) and `V3a` (deep/anterior).
  4. **Indexing Check**: Sort units by NWB index within each probe to match local indices in raw `.npy` arrays.

### Timing & Synchronization Issues
- **Reference Anchor**: Always align trials to **Code 101.0** (Presentation 1 Onset = 0ms).
- **Photodiode Drift**: Check photodiode events for physical stimulus onset jumps. V1 spiking should peak at $40\text{–}60\text{ ms}$ post-jump.

### Empty or NaN Plots
- **Prevention**: Use `np.nan_to_num()` when summarizing and averaging metrics.
- **Save Guard**: The pipeline enforces a check preventing empty/zero-variance arrays from saving plots.

---

## 2. 15-Step Pipeline Protocol

| Step | Phase | Purpose |
|:---:|:---|:---|
| **1** | **Validation** | Verify NWB schema and verify essential fields are present. |
| **2** | **Events** | Build omission windows relative to expected stimulus timing. |
| **3** | **QC** | Filter channels (remove bad channels with $> 4\text{ SD}$ variance/noise). |
| **4** | **Extraction** | Extract trial-level LFP and MUAe epochs. |
| **5** | **Normalization** | Baseline normalize signals to decibels (dB). |
| **6** | **TFR** | Compute Time-Frequency Representations per condition. |
| **7** | **Contrast** | Compute contrast (e.g. Standard vs Omission delta power). |
| **8** | **Correlation** | Compute inter-channel spectral correlation matrices. |
| **9** | **Coherence** | Compute inter-area coherence spectra. |
| **10** | **Network** | Generate adjacency matrices for network connectivity graph analyses. |
| **11** | **Granger** | Compute Granger causality using VAR models. |
| **12** | **Statistics** | Run 2D cluster-based permutation tests. |
| **13** | **Hierarchy** | Group results into low-level visual, mid-level visual, and prefrontal tiers. |
| **14** | **Adaptation** | Track adaptation rates and response attenuation. |
| **15** | **Manifest** | Write summary manifests and output reports to target vault folders. |
