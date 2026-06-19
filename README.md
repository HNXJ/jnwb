# Omission: Hierarchical Visual Prediction Pipeline

Canonical repository for the **Omission** project, implementing a large-scale neurophysiological investigation into hierarchical V1-PFC (1-11) visual prediction. This repository isolates "ghost signals" — top-down neural representations of predicted but absent stimuli — across the cortical hierarchy.

## 🏗️ Repository Architecture

- **`src/`**: Modular analytical logic and figure generators.
  - `analysis/`: Functional core (LFP, Spiking, IO, Visualization).
  - `f001_theory/` through `f050_laminar_analysis/`: Canonical standardized analysis modules for publication figures.
    - **1-11**: Core Spiking, Spectral, and Laminar Routing.
    - **12-15**: Functional Connectivity (MI) and Network Dynamics.
    - **16**: Impedance Tensor Estimation.
    - **17-25**: Surprise Scaling, Ghost Signals, PAC, Effective Connectivity, Pupil Decoding.
    - **26-50**: State Dynamics, Identity Coding, Cross-Area Manifolds, and Laminar Refinements.
  - `scripts/`: Pipeline entrypoints (e.g., `run_pipeline.py`).
- **`context/`**: Foundational mandates, session-area mapping, and session-by-session logs.
  - `overview/`: Project purpose, data availability, and anatomical area mappings.
  - `specs/`: Canonical task definitions, 15-step pipeline standards, and style mandates.
  - `analysis/`: Strategic roadmaps and methodology-specific sub-documentation.
  - `operations/`: Troubleshooting logs and implementation history.

## 🚀 Canonical Pipeline

The master pipeline implements a rigorous **15-step LFP-NWB protocol** to generate publication-grade results from raw neurophysiological data.

1. **Validation**: NWB schema enforcement.
2. **Events**: Omission window and ghost signal encoding.
3. **QC**: Per-channel variance/noise check + Bipolar referencing.
4. **Extraction**: Matched epoch alignment.
5. **Normalization**: dB relative to [-250, -50]ms baseline.
6. **TFR**: Time-Frequency Representations (Hanning/Spectrogram).
7. **Contrast**: Omission vs. Control Δ-power.
8. **Correlation**: Inter-area spectral correlation.
9. **Coherence**: Phase-Locking Value (PLV) spectra.
10. **Network**: Band-limited adjacency matrices.
11. **Granger**: Directional causality (Wilson method).
12. **Statistics**: 2D Cluster-based permutation testing.
13. **Hierarchy**: Tier-based (Low/Mid/High) aggregation.
14. **Adaptation**: Post-surprise quenching tracking.
15. **Manifest**: Reproducibility JSON + Summary CSV.

Run the full pipeline:
```bash
python -m src.main --run-all
```

## 🛠️ Engineering Standards

- **Python Environment**: Python 3.14 exclusively.
- **Plotting**: Interactive Plotly HTML (Kaleido-Free).
- **Aesthetic**: Madelane Golden Dark theme (`#CFB87C` / `#9400D3`).
- **Statistical Hygiene**: Cluster-based permutation for FWER control; Functional SNR > 1.0 thresholding.
- **Root Hygiene**: No new files on root; operations restricted to proper subdirectories.
- **Verbosity**: Extreme code verbosity (every operation must be printed/logged).

## 📄 Documentation

Refer to `context/specs/root_files__INDEX.md` for a comprehensive directory of all active documentation and specifications.
