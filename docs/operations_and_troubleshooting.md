# Omission Operations & Troubleshooting

This document outlines common pipeline troubleshooting steps, anatomical mapping rules, and the 15-Step LFP-NWB Analysis pipeline standards.

---

## 1. Troubleshooting & Debugging

### The "Zero Neuron" & Missing Area Bug
- **Symptoms**: Areas like `V3d`, `TEO`, or `FST` show zero units or are missing from plots.
- **Root Cause**: Reliance on hardcoded or incomplete metadata registries; failure to parse multi-area descriptors (e.g. `V1, V2` labels).
- **Anatomical Mapping Rules**:
  1. **Probe Identification**: The current jnwb code (`jnwb.addressing.map_peak_channel_to_area`) resolves area/probe directly from the electrodes table's `location`/`area`/`group_name` column, not via a `peak_channel_id // 128` formula - no such formula was found anywhere in the current codebase during a 2026-07-12 audit. Treat this line as describing a legacy/archived approach, not current behavior, until a real channel-arithmetic probe-ID function is confirmed to exist.
  2. **Multi-Area Segment Split**: `scripts/build_session_sidecars.py` divides a probe's local channel index by `len(areas) // 128` to assign an area label from an ordered area list.
  3. **V3 Special Case**: Per `jnwb.sequence_layout.py`, channels 1-64 of a `V3`-labeled probe map to `V3d`, channels 65-128 map to `V3a`. `V3d`/`V3a` are distinct cortical **areas** (dorsal/anterior V3 subdivisions), not a superficial/deep **layer** split - do not conflate this with the separate superficial-vs-deep layer classification (`jnwb.addressing.classify_layer_from_depth`, z-depth threshold).
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
