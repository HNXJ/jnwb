---
status: canonical
scope: analysis
source_of_truth: true
supersedes:
  - context/specs/archive__legacy-plans__omission-plan.md
  - context/specs/archive__legacy-plans__omission-analysis-plan.md
  - context/specs/archive__legacy-plans__lfp-analysis-roadmap.md
  - context/specs/archive__legacy-plans__next-steps-plan.md
  - context/specs/archive__legacy-plans__progress-details.md
last_reviewed: 2026-04-06
---

# Analysis Roadmap: The Cortical Hierarchy of Expectation

## 1. Strategic Objective
To quantify the cortical hierarchy of expectation using multi-scale neurophysiology, characterizing the oscillatory fingerprints of the "Visual Void" and mapping the coordination between local field potentials (LFP) and single-unit activity (SPK) across 11 brain areas.

## 2. Core Analytical Framework
### 2.1 Standardized Frequency Bands
- **Theta ($\theta$):** 4–8 Hz
- **Alpha ($\alpha$):** 8–13 Hz
- **Beta ($\beta$):** 13–30 Hz (Top-down prediction / Feedback)
- **Low Gamma ($\gamma_L$):** 35–55 Hz (Feedforward error)
- **High Gamma ($\gamma_H$):** 65–100+ Hz

### 2.2 Signal Logic & Normalization
- **Tools**: Complex Morlet Wavelets (7 cycles) or Multi-taper decomposition.
- **Normalization**: Decibel change ($10 \cdot \log_{10}(P/P_{base})$) relative to fixation baseline (-500 to 0ms).
- **Smoothing**: Gaussian kernels for PSTHs and spike counts to prevent phase shifts.

## 3. Completed Work (Summary)
### Step 1: Classification & Behavioral Proxies
- **Figure 1**: Grand Average Firing Rates (RRRR vs. Omission).
- **Figure 2**: Pupil & Eye Decoding of surprise and identity.
- **Figure 3**: Neural Identity Decoding (A vs. B).
- **Figure 4**: Omission Detection (Omit vs. Delay).

### Step 2: Population Dynamics & Stability
- **Figure 5**: Hierarchical Mean-Matched Fano Factor (MMFF) quenching.
- **Figure 6**: Unit Functional Classification (Omit+, Stim+/-, Null).
- **Figure 7**: Population Manifolds (PCA/UMAP) and state-space trajectories.

### Step 3: Latency & Information Hubs
- **Figure 8**: Surprise Latency Hierarchy (Evidence for Top-Down propagation).
- **Figure 9**: Individual Information Mapping (Single-unit vs. LFP decoding).

## 4. Active & Future Work
### Step 4: Multi-Scale Connectivity (LFP-focused)
- **Figure 10**: Spectral Fingerprints (TFR grids per area).
- **Figure 11**: Phase-Amplitude Coupling (PAC) shifts during surprise.
- **Figure 12**: Inter-Regional Coherence (PFC-V1 synchrony).
- **Figure 13**: Spike-LFP Phase Locking (Pairwise Phase Consistency).
- **Figure 14**: Network Granger Causality Graphs (Directional adjacency).

### Step 5: Behavioral Fine-Mapping
- **Figure 16**: Eye-Movement Identity Decoding (High-dim kinetics).
- **Figure 17**: Systematic Content Decoding (Oculomotor evidence for internal models).

## 6. Audit Inventory (April 2026)
The following technical inconsistencies were identified and resolved during the Step 1 organization pass:
- **Timings**: Standardized p1=0, p2=1031, p3=2062, p4=3093 (ms relative to p1).
- **Pupil Mapping**: Confirmed as Channel 2 in `.npy` behavioral files.
- **Theme**: Unified to `plotly_white` for all publication-grade figures.
- **Sanitation**: Mandatory `np.nan_to_num` for all spectral and spiking summaries.

## 7. Risks & Blockers
- **Laminar Crossover**: Automated sink-detection is prone to artifacts; manual verification of CSD heatmaps is required.
- **Data Scalability**: Monolithic pickle files (`global_processed_data`) are a bottleneck; migration to HDF5/Zarr is recommended for Stage 3.
- **Statistical Power**: Some areas in specific sessions (e.g., 230630) have low unit counts, requiring robust hierarchical aggregation.

