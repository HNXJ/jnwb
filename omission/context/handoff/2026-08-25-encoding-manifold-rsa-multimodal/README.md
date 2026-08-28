# Handoff Handout: Encoding Manifolds, Sequence RSA, and Multimodal Latent Fusion

**Date:** 2026-08-25  
**Workspace:** `c:/workspace/jnwb/omission`  
**Status:** Figure 04 Sealed & Audited; Unified Manifold Engine, Sequence RSA, and Multimodal Battery Completed.  
**Audience:** Next engineering / analysis agent resuming work in this workspace.

---

## 1. Executive Summary of Achievements

Over the preceding sessions, the following major scientific and statistical milestones were achieved, verified, and sealed:

1. **Figure 04 Sealed & Audited**:
   - Closed Benjamini-Hochberg FDR correction on full-corpus 4-way temporal context sequence decoding ($43/79$ populations, $54.4\%$ survive FDR at $q < 0.05$).
   - Explicit scope differentiation rendered across all 9 panels: Full-Corpus ($N=22$ sessions, $n=79$ areas) vs Representative Manifold Search ($N=4$ multi-area sessions, $n=960$ decoding runs).
   - Rendered publication-grade figures: `outputs/draft-01/fig04/fig04_finalized.png` and `.svg`.

2. **Nested $\operatorname{PCA}[N] \times \operatorname{UMAP}[M] \times \operatorname{Encoder}[E]$ Phase Diagram**:
   - Evaluated 3,745 manifold points under strict nested LOCO cross-validation (Outer LOCO Test $\supset$ Inner 3-Fold CV Hyperparameter Selection).
   - Proved physical stimulus occupies a broad, stable low-dimensional basin ($N^* \in [5, 30], M^* \in [2, 5]$), whereas omission identity ($X|A$ vs $X|B$) is uniformly flat at chance ($\operatorname{Perf}_{\text{nested}} = 0.5128$) with high selection entropy ($\mathcal{H}_M = 1.255$).

3. **$12 \times 12$ Condition Representational Similarity Analysis (RSA)**:
   - Decomposed population geometry across 3 slot positions ($p_2, p_3, p_4$) $\times$ 4 sequence conditions ($\text{AAAB}, \text{AABA}, \text{BBBA}, \text{BBAB}$).
   - **Position Model**: $\beta = +0.5772, p_{\text{perm}} = 0.000000$ (Dominant geometry).
   - **Physical Stimulus Identity**: $\beta = +0.3196, p_{\text{perm}} = 0.034286$ (Significant).
   - **Expected Identity during Omission**: $\beta = +0.4665, p_{\text{perm}} = 0.168571$ (Non-significant).

4. **Balanced Multimodal Latent Fusion ($[\operatorname{PCA}(X_S), \operatorname{PCA}(X_L)] \rightarrow \operatorname{UMAP}_M$)**:
   - Matched 31 recording cells across 15 sessions.
   - Proved multimodal synergy on sensory-driven trials ($\text{AUC} = 0.8668$, $\Delta_L = +0.0632, \Delta_S = +0.0723, p < 0.005$).

5. **Predictability Context Discovery ($X|\text{Structured}$ vs $X|R$)**:
   - While specific phantom identity ($X|A$ vs $X|B$) is null, **Rule vs Random context ($X|\text{Structured} \text{ vs } X|R$) is robustly encoded** during identical visual silence ($\text{AUC} = 0.8098$, $p_{\text{perm}} = 0.000000$).

---

## 2. Key File Locations & Provenance

### Source Code & Execution Scripts
- [`scripts/unified_manifold_encoder_engine.py`](file:///c:/workspace/jnwb/omission/scripts/unified_manifold_encoder_engine.py): The frozen reusable statistical engine $\mathcal{E}(X, Z, G) \rightarrow \{H_{\text{val}}, H_{\text{test}}, G_{\text{gap}}, N^*, M^*, E^*, P_{\text{perm}}, \text{CI}_{\text{CP}}, \Delta\}$.
- [`scripts/compute_fig04_nested_manifold_surface.py`](file:///c:/workspace/jnwb/omission/scripts/compute_fig04_nested_manifold_surface.py): Evaluates the 2D $(N, M)$ manifold parameter surface.
- [`scripts/run_pca_umap_lfp_and_multimodal.py`](file:///c:/workspace/jnwb/omission/scripts/run_pca_umap_lfp_and_multimodal.py): Runs matched 31-cell $\operatorname{PCA} \rightarrow \operatorname{UMAP}$ on SPK, LFP, and balanced fusion.
- [`scripts/compute_sequence_rsa_and_multimodal_fusion.py`](file:///c:/workspace/jnwb/omission/scripts/compute_sequence_rsa_and_multimodal_fusion.py): Computes the $12 \times 12$ RSA multiple regression and state trajectories.
- [`scripts/compute_predictable_vs_random_omission_decoding.py`](file:///c:/workspace/jnwb/omission/scripts/compute_predictable_vs_random_omission_decoding.py): Evaluates rule vs random omission context decoding ($X|\text{Structured}$ vs $X|R$).
- [`scripts/generate_fig04_complete_figure.py`](file:///c:/workspace/jnwb/omission/scripts/generate_fig04_complete_figure.py): Renders the unified $3 \times 3$ Figure 04 and subplots.

### Data Receipts & Output Tables
- [`outputs/classification/fig04_temporal_context_fdr_audit.csv`](file:///c:/workspace/jnwb/omission/outputs/classification/fig04_temporal_context_fdr_audit.csv): FDR-corrected temporal context $p$-values ($n=79$).
- [`outputs/classification/fig04_diagnostics/pca_umap_surface_grid.csv`](file:///c:/workspace/jnwb/omission/outputs/classification/fig04_diagnostics/pca_umap_surface_grid.csv): 3,745 surface evaluation points.
- [`outputs/classification/fig04_diagnostics/fig04_pca_umap_phase_diagram.png`](file:///c:/workspace/jnwb/omission/outputs/classification/fig04_diagnostics/fig04_pca_umap_phase_diagram.png): Manifold phase diagram heatmaps.
- [`outputs/classification/fig04_rsa_model_regression.csv`](file:///c:/workspace/jnwb/omission/outputs/classification/fig04_rsa_model_regression.csv): RSA multiple regression betas & $p$-values.
- [`outputs/classification/fig04_rsa_multimodal_synthesis.png`](file:///c:/workspace/jnwb/omission/outputs/classification/fig04_rsa_multimodal_synthesis.png): 3-panel RSA & Multimodal synthesis.
- [`outputs/classification/predictable_vs_random_omission_results.csv`](file:///c:/workspace/jnwb/omission/outputs/classification/predictable_vs_random_omission_results.csv): Predictable vs Random omission decoding.
- [`outputs/classification/unified_multimodal_summary.json`](file:///c:/workspace/jnwb/omission/outputs/classification/unified_multimodal_summary.json): Exact Clopper-Pearson binomial prevalence receipts.
- [`outputs/draft-01/fig04/fig04_finalized.png`](file:///c:/workspace/jnwb/omission/outputs/draft-01/fig04/fig04_finalized.png) / [`.svg`](file:///c:/workspace/jnwb/omission/outputs/draft-01/fig04/fig04_finalized.svg): Sealed Figure 04.

### Labyrinth Nodes Recorded
- `artifacts/.lab/f04-sealed-audit-20260824.json`: Sealed Figure 04 audit record.
- `artifacts/.lab/f04-pca-umap-phase-diagram-receipt-20260824.json`: Nested PCA x UMAP phase diagram receipt.
- `artifacts/.lab/f04-f07-rsa-multimodal-fusion-receipt-20260824.json`: Sequence RSA and balanced multimodal fusion receipt.
- `artifacts/.lab/f04-predictable-vs-random-context-receipt-20260824.json`: Predictable vs Random omission context receipt.

---

## 3. Mandatory Scientific Invariants & Language Rules

1. **Strict Terminology Invariants**:
   - **Never say:** "Omission identity is absent" $\rightarrow$ **Strictly use:** *"Omission identity was not detectably represented in scalar firing rates, spatiotemporal linear subspaces, or the tested low-dimensional nonlinear population manifolds."*
   - **Never call $p_4$ a boundary artifact:** $\rightarrow$ **Strictly use:** *"Terminal-position-specific structure because cross-position generalization collapses ($0.387$, $0.0\%$ significance)."*
   - **PCA Subspace:** *"$\operatorname{PCA}_5$ preserved the measured held-out stimulus-decoding performance of the ambient representation ($0.8303$ vs $0.8270$)."*
2. **Safe HDF5 IO**:
   - Always open NWB files using context managers (`with h5py.File(...) as f:` or `with NWBHDF5IO(...) as io:`) to avoid Windows file locks.
3. **Canonical Truth Precedence**:
   - Raw data / receipts $>$ `PROJECT_STATE.md` $>$ Narrative memory.

---

## 4. Immediate Next Steps for the Next Agent

The next agent should proceed to the systematic assembly and finalization of **Figures 05, 06, and 07**:

### Step 1: Figure 05 (LFP Spectrotemporal Dynamics & Laminar Modulation)
- Audit candidate panels `F05-P001` through `F05-P017` in `outputs/panel_atlas/F05/`.
- Assemble the canonical $3 \times 3$ layout:
  - Panel A: Broadband spectrogram (0–100 Hz) stimulus vs omission.
  - Panel B: Theta power enhancement (3–8 Hz).
  - Panel C: Gamma power suppression (30–80 Hz).
  - Panel D: Alpha/Beta dynamics (8–30 Hz).
  - Panel E: Cortical hierarchy breakdown across 6 areas.
  - Panel F: Stimulus vs Omission effect size comparison (Cohen's $d$).
  - Panel G: GLMM Model C estimates & animal random effects.
  - Panel H: Surface Laplacian volume conduction controls.
  - Panel I: Summary matrix of spectrotemporal modulation.
- Render `outputs/draft-01/fig05/fig05_finalized.png` and `.svg`.

### Step 2: Figure 06 (Spike-LFP Spectral Geometry & Cross-Frequency Coordination)
- Assemble the reference geometry findings ($O-B$ vs $O-S$ algebra proving theta concordance $r=+0.512$ is pure omission dynamics).
- Render `outputs/draft-01/fig06/fig06_finalized.png` and `.svg`.

### Step 3: Figure 07 (Joint Spiking vs LFP Information & Substrate Complementarity)
- Integrate the balanced multimodal latent fusion receipts ($\text{AUC} = 0.8668$, $\Delta_L = +0.0632, \Delta_S = +0.0723$, PCA-5 matched control) and regional confounding analysis for the 31 matched recording cells.
- Render `outputs/draft-01/fig07/fig07_finalized.png` and `.svg`.
