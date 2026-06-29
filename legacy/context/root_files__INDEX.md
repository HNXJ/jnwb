# Documentation Index

This index provides a one-line description of every active document in the `context/` directory.

## 🟢 Overview (Canonical)
- **`overview/project-overview.md`**: Core project purpose, scientific questions, and directory map. (Source of Truth)
- **`overview/data-availability.md`**: Summary of 13 sessions and available data modalities. (Source of Truth)
- **`overview/session-area-mapping.md`**: Anatomical probe-to-area mapping logic and master table. (Source of Truth)
- **`overview/session-condition-trial-info.md`**: Detailed trial counts (960/session) and condition distribution.
- **`overview/nwb-data-oglo-session-by-session.md`**: Raw session-by-session NWB data logs and timestamps.
- **`overview/nwb-data-oglo-session-by-session-table.md`**: Tabular summary of NWB session metadata.

## 🔵 Specs (Canonical)
- **`specs/task-specification.md`**: Detailed stimulus sequence, condition logic, and omission definitions. (Source of Truth)
- **`specs/pipeline-standard.md`**: The 15-step LFP-NWB analysis protocol (includes reproducibility standards). (Source of Truth)
- **`specs/supplemental-figure-mandate.md`**: SF1–SF13 supplemental figure logic and method mandates. (Source of Truth)
- **`specs/figure-style-mandate.md`**: All plotting rules, color palettes, and epoch windows. (Source of Truth)
- **`specs/nwb-table-sessions-probes-areas.md`**: Raw NWB-extracted probe/area channel table.

## 🟡 Analysis (Working/Canonical)
- **`analysis/roadmap.md`**: Strategic objective, completed work (Figs 1-9), and future phases (10-17). (Source of Truth)
- **`analysis/population-audit.md`**: Comprehensive tiered census of omission neurons across all 11 areas.
- **`analysis/unit-hierarchical-comparison.md`**: High-stringency hierarchy comparison of O+ neurons.
- **`analysis/decoding-framework.md`**: Principles and targets for the 108-test neural/behavioral decoding matrix.
- **`analysis/methods-spiking.md`**: Methodology for single-unit and population dynamics (SVM, PCA, Latency).
- **`analysis/methods-spectral.md`**: Methodology for TFR, dB normalization, and variability quenching (MMFF/MMV).
- **`analysis/methods-rsa-cka.md`**: Representational Similarity Analysis and Centered Kernel Alignment standards.
- **`analysis/methods-behavior.md`**: Oculomotor analysis rules (DVA, Pupil, Saccades).

## 🟣 Manuscript & Verification (Working)
- **`manuscript/results-summary.md`**: Synthesis of global findings for Figures 1-6. (Source of Truth)
- **`manuscript/analysis-spec.md`**: Implementation specification for manuscript Figures 1-4.
- **`manuscript/poster-01.md`**: Content for Neural Dynamics/Spectral Omission poster.
- **`manuscript/poster-02.md`**: Content for Oscillations/Predictive Routing poster (intl. collab).

## 🔴 Operations (Working)
- **`operations/troubleshooting.md`**: Solutions for common bugs (mapping, timing, NaNs). (Source of Truth)
- **`operations/implementation-history.md`**: Historical log of pipeline development phases (1-5).

## ⚪ Navigation & Meta
- **`migration-note.md`**: Detailed record of the context/ cleanup pass decisions.
- **`root_files__omission_analysis_guide.md`**: Production-grade NWB atlas + omission neuron + waveform + vFLIP2 spectrolaminar analysis guide (implementation-ready).
- **`README.md`**: Top-level directory guide and repository conventions.
- **`archive/notes/vmemory-archived.md`**: Archived copy of root VMEMORY snapshot.
