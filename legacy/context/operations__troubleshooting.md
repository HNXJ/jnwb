---
status: canonical
scope: operations
source_of_truth: true
supersedes:
  - context/docs/notes/crucial-debugging-notes.md
last_reviewed: 2026-04-06
---

# Troubleshooting & Debugging: Omission Project

## 1. Mapping & Identity Issues
### The "Zero Neuron" & Missing Area Bug
- **Symptoms**: Areas like V3d, TEO, FST showed zero units or missed data during plotting.
- **Root Cause**: Reliance on incomplete summary JSONs instead of NWB metadata; failure to split combined labels (e.g., "V1, V2").
- **Solution**: Implemented the **Definitive Mapping Rules**:
  1. **Probe ID**: `peak_channel_id // 128`
  2. **Multi-Area Split**: Divide 128 channels into N equal segments per label.
  3. **V3 Special Case**: Segment split 50/50 between V3d and V3a.
  4. **Global vs. Local Indexing**: Group units by probe and sort by NWB index to match `.npy` array local indices.

## 2. Timing & Synchronization
### Physiological Lag Verification
- **Standard**: V1 response peaks at 40-60ms post-photodiode jump.
- **Reference**: Use **Code 101.0** (P1 onset) as the absolute anchor. Avoid trial `start_time` for alignment.

## 3. Data Integrity
### Empty or NaN Plots
- **Constraint**: Mandatory `np.nan_to_num` for all summaries.
- **Guard**: The pipeline will not save plots that are all-zero or all-NaN to prevent "vault contamination."

## 4. Scalability & Performance
### Pickle Serialization Bottleneck
- **Issue**: Serialization of the monolithic `global_processed_data` dictionary via `pickle` causes I/O overhead.
- **Recommendation**: Transition to HDF5 or Zarr for Stage 3 connectivity results.
