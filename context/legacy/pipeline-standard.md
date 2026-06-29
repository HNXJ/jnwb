---
status: canonical
scope: specs
source_of_truth: true
supersedes:
  - context/specs/archive__legacy-plans__nwb-pipeline-standard.md
  - context/specs/archive__legacy-plans__lfp-nwb-pipeline-standard.md
  - context/specs/archive__legacy-plans__15-step-lfp-pipeline.md
last_reviewed: 2026-04-06
---

# Pipeline Standard: 15-Step LFP-NWB Analysis

This document formalizes the 15-step pipeline for the Sequential Visual Omission Task, ensuring consistent processing across all 13 recording sessions.

## 1. Common NWB Contract & Schema
All analysis must start with the **Golden Standard** alignment: **Code 101.0 (Presentation 1 Onset) = 0ms**.
- **Schema Validation**: Every session must be validated against a canonical dictionary containing: `session_id`, `nwb_path`, `lfp`, `electrodes`, `trials`, `areas`, `channels`, `photodiode`, `fs`, and `channel_depths`.

## 2. Event Timeline & Extraction Rules
The canonical sequence is: `fixation` -> `p1` -> `d1` -> `p2/om` -> `d2` -> `p3/om` -> `d3` -> `p4/om` -> `d4` -> `reward`.
- **Standard Window**: 6000ms total, with a 1000ms pre-stimulus buffer relative to Code 101.0.
- **Ghost Signal**: Omission windows must be matched to the timing of the expected stimulus onset to isolate pure top-down signals.

## 3. The 15-Step Protocol
| Step | Phase | Function / Purpose |
|:---:|:---|:---|
| 1 | **Validation** | `validate_session_schema`: NWB schema enforcement. |
| 2 | **Events** | `build_omission_windows`: Event timeline and ghost signal encoding. |
| 3 | **QC** | `run_lfp_qc`: Per-channel QC (variance, noise) + Bipolar referencing. |
| 4 | **Extraction** | `extract_matched_epochs`: Aligned trial-level LFP tensors. |
| 5 | **Normalization** | `normalize_epochs`: Baseline normalization (dB default). |
| 6 | **TFR** | `compute_tfr_per_condition`: Time-Frequency Representations (Hanning/Spectrogram). |
| 7 | **Contrast** | `compute_band_contrast`: Omission vs. Control Δ-power per band. |
| 8 | **Correlation** | `compute_spectral_corr`: Inter-area spectral correlation matrices. |
| 9 | **Coherence** | `compute_all_pairs_coherence`: Inter-area coherence spectra. |
| 10 | **Network** | `build_coherence_network_data`: Band-limited adjacency matrices (Beta/Gamma). |
| 11 | **Granger** | `compute_spectral_granger`: Directional GC (VAR-based Wilson method). |
| 12 | **Statistics** | `run_cluster_permutation`: 2D Cluster-based permutation testing. |
| 13 | **Hierarchy** | `aggregate_by_tier`: Low/Mid/High hierarchy tier comparisons. |
| 14 | **Adaptation** | `compute_post_omission_adapt`: Post-surprise quenching/adaptation tracking. |
| 15 | **Manifest** | `write_analysis_manifest`: Reproducibility JSON + Summary CSV. |

## 4. Preprocessing & Shared Metrics
- **Bipolar Referencing**: Apply to reduce volume conduction and reference contamination.
- **QC Threshold**: Passed if <10% channels are bad.
- **Normalization**: `10 * log10(P / Pbase)` (dB).

## 5. Frequency Band Definitions
| Band | Range (Hz) | Functional Interpretation |
|:---|:---:|:---|
| **Theta** | 4 – 8 | Coordination / State modulation |
| **Alpha** | 8 – 13 | Inhibitory modulation |
| **Beta** | **13 – 30** | **Top-down prediction / Feedback** |
| **Gamma** | 35 – 70 | Bottom-up sensory drive / Feedforward |

## 6. Validation Checkpoints
- **V1 Timing**: First significant peak at 40-60ms post-photodiode jump.
- **Ghost Signal**: Verify identical gray-screen input during omission windows.
- **Statistical Hygiene**: Use cluster-based permutations to control for FWER.

## 7. Outputs & Artifacts
- **JSON Manifest**: Records `fs`, `nperseg`, bands, and conditions used.
- **CSV Summary**: Band-limited power and coherence metrics for group-level analysis.
- **Plots**: TFR grids, network adjacency graphs, and Granger directionality diagrams.
  - **Mandate**: All figures MUST strictly adhere to `context/specs/figure-style-mandate.md` (e.g., Arial/Helvetica, p1-relative timing, standardized Omission color system).
