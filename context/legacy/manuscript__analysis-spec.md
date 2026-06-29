# Analysis Specification: Omission Publication Manuscript
This specification outlines the data analysis pipeline corresponding to the schematic publication figures.

## Figure 1: Paradigm and Theoretical Grounding
- **Task**: Standardize NWB probe/area mapping and CSD profile extraction.
- **Tools**: `get_unit_to_area_map`, `omission_hierarchy_utils.py`
- **Output**: Multi-panel visualization of recording geometry and task architecture.

## Figure 2: Local Network Responses
- **Task**: Compute population-averaged, layer-specific TFR spectrograms locked to omission onset.
- **Analysis**: Omission vs. Stimulus contrast in dB scale; High-gamma power dynamics (CSD-verified).
- **Tools**: `lfp_tfr.py`, `generate_figure_6.py`

## Figure 3: Population State-Space Dynamics
- **Task**: Dimensionality reduction (PCA) of population trajectories during omission window.
- **Analysis**: Divergence analysis; Mahalanobis distance between stimulus and omission states.
- **Tools**: `run-manifold-suite-comprehensive.py`

## Figure 4: Inter-areal / Laminar Rhythm Coordination
- **Task**: Spike-Field Coherence (SFC) for Omission vs. Population neurons.
- **Rigour**: Pairwise Phase Consistency (PPC) to correct for spike sparsity.
- **Analysis**: Band-specific phase-locking (Alpha/Beta vs. Gamma) during omission windows.
- **Tools**: `spike_lfp_coordination.py`, `generate_figure_8.py`
