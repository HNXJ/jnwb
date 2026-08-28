#!/usr/bin/env python3
"""Organize omission outputs folder into exactly 7 clean top-level directories.

Structure:
omission/outputs/
  ├── draft-01/
  │    ├── fig01/ ... fig07/ (each with code/, readme.md, assets/, subplots/)
  │    ├── sfig01/ ... sfig33/ (supplementary figures)
  │    ├── manuscript-docx/ (master docx & pdf package)
  │    └── contexts-methods.md (comprehensive methods & context)
  ├── panel_atlas/ (candidate panels F04-F07, registry, contact sheets)
  ├── classification/ (unit inclusion, decoding tables, SSA, class knockouts)
  ├── lfp_dynamics/ (TFR condition maps, census GLMM, power dynamics)
  ├── substrates/ (F06 matched substrate, F07 multimodal substrate & receipts)
  ├── connectivity/ (spike-LFP coupling, Granger networks, LFP-LFP coherence)
  └── exploratory/ (visualization gallery, raster suites, diagnostic suites)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]

OUTPUTS = OA_ROOT / "outputs"
CONTEXT = OA_ROOT / "context"
FIG_SRC = CONTEXT / "figures"
DOCX_SRC = CONTEXT / "manuscript-docx"

# 7 Top-Level Targets
DRAFT01 = OUTPUTS / "draft-01"
PANEL_ATLAS = OUTPUTS / "panel_atlas"
CLASSIFICATION = OUTPUTS / "classification"
LFP_DYNAMICS = OUTPUTS / "lfp_dynamics"
SUBSTRATES = OUTPUTS / "substrates"
CONNECTIVITY = OUTPUTS / "connectivity"
EXPLORATORY = OUTPUTS / "exploratory"

TARGET_7 = [DRAFT01, PANEL_ATLAS, CLASSIFICATION, LFP_DYNAMICS, SUBSTRATES, CONNECTIVITY, EXPLORATORY]


def ensure_dirs():
    for d in TARGET_7:
        d.mkdir(parents=True, exist_ok=True)


def build_figure_folder(fig_num: str, src_dir_name: str):
    fig_dest = DRAFT01 / f"fig{fig_num}"
    code_dir = fig_dest / "code"
    assets_dir = fig_dest / "assets"
    subplots_dir = fig_dest / "subplots"
    
    for d in [code_dir, assets_dir, subplots_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    src_dir = FIG_SRC / src_dir_name
    if not src_dir.exists():
        print(f"Warning: source dir {src_dir} not found.")
        return
        
    # Copy code
    for py_file in src_dir.glob("*.py"):
        shutil.copy2(py_file, code_dir / py_file.name)
        
    # Copy readme
    readme_src = src_dir / "README.md"
    if readme_src.exists():
        shutil.copy2(readme_src, fig_dest / "README.md")
    else:
        (fig_dest / "README.md").write_text(f"# Figure {fig_num}\n\nGenerated from `{src_dir_name}`.\n")
        
    # Copy assets (main figure PNG, SVG, PDF, receipt.json)
    for ext in ["*.png", "*.svg", "*.pdf", "*.receipt.json", "*.json"]:
        for asset in src_dir.glob(ext):
            if asset.name.startswith(f"fig{fig_num}"):
                shutil.copy2(asset, assets_dir / asset.name)
            elif asset.name.endswith(".json") and "receipt" in asset.name:
                shutil.copy2(asset, assets_dir / asset.name)
                
    # Copy subplots
    sub_svg = src_dir / "svg"
    if sub_svg.exists() and sub_svg.is_dir():
        for item in sub_svg.iterdir():
            if item.is_file():
                shutil.copy2(item, subplots_dir / item.name)
                
    sub_artifacts = src_dir / "artifacts"
    if sub_artifacts.exists() and sub_artifacts.is_dir():
        for item in sub_artifacts.iterdir():
            if item.is_file():
                shutil.copy2(item, subplots_dir / item.name)
                
    # Also copy any subpanel images like fig03A, fig03B...
    for p in src_dir.glob(f"fig{fig_num}[A-Z]*.*"):
        shutil.copy2(p, subplots_dir / p.name)
        
    print(f"Created {fig_dest} with code/, assets/, subplots/, and README.md")


def build_supplement_folders():
    supp_dir = FIG_SRC / "supplements"
    if not supp_dir.exists():
        print(f"Warning: {supp_dir} not found.")
        return
        
    # SFIG01 to SFIG33 from figS01 .. figS33
    for s_idx in range(1, 34):
        s_str = f"{s_idx:02d}"
        sfig_dest = DRAFT01 / f"sfig{s_str}"
        sfig_assets = sfig_dest / "assets"
        sfig_code = sfig_dest / "code"
        sfig_subplots = sfig_dest / "subplots"
        
        for d in [sfig_assets, sfig_code, sfig_subplots]:
            d.mkdir(parents=True, exist_ok=True)
            
        matching_files = list(supp_dir.glob(f"figS{s_str}_*.*")) + list(supp_dir.glob(f"figS{s_idx}_*.*"))
        for f in matching_files:
            shutil.copy2(f, sfig_assets / f.name)
            
        (sfig_dest / "README.md").write_text(
            f"# Supplementary Figure S{s_str}\n\nAssets: `assets/`\nSource: `context/figures/supplements/`\n"
        )
        
    # Additional named supplements
    named_supps = [
        ("sfig_qc_lfp_artifacts", "supplement_lfp_artifact_qc"),
        ("sfig_identity_reversal", "supp_identity_reversal_generalization"),
        ("sfig_band_hierarchy", "band_power_hierarchy_supplement"),
        ("sfig_lfp_connectivity", "lfp_lfp_connectivity_supplement"),
        ("sfig_spk_coupling", "spk_spk_coupling_supplement"),
    ]
    for dest_name, src_name in named_supps:
        src = FIG_SRC / src_name
        if src.exists():
            dest = DRAFT01 / dest_name
            dest.mkdir(parents=True, exist_ok=True)
            for item in src.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest / item.name)
                elif item.is_dir() and item.name != "__pycache__":
                    shutil.copytree(item, dest / item.name, dirs_exist_ok=True)
            print(f"Copied named supplement {src_name} -> {dest}")


def copy_manuscript_docx():
    dest = DRAFT01 / "manuscript-docx"
    dest.mkdir(parents=True, exist_ok=True)
    if DOCX_SRC.exists():
        for item in DOCX_SRC.iterdir():
            if item.is_file():
                shutil.copy2(item, dest / item.name)
        print(f"Copied manuscript-docx package to {dest}")


def compile_contexts_methods():
    methods_file = DRAFT01 / "contexts-methods.md"
    
    sections = []
    sections.append("# Omission: Experimental Contexts, Paradigm, and Analysis Methods\n")
    sections.append("**Draft Compilation:** `draft-01` | **Date:** 2026-08-24\n")
    sections.append("---\n")
    
    # Read numbered context files if available
    for num in range(10):
        matches = list(CONTEXT.glob(f"{num:02d}_*.md"))
        if matches:
            content = matches[0].read_text(encoding="utf-8", errors="ignore")
            sections.append(f"\n## {matches[0].stem}\n\n{content}\n")
            
    # Also add core summary of methods
    methods_summary = """
## Consolidated Scientific & Statistical Methods

### 1. Task Paradigm & Trial Design
Trials consist of sequential visual presentations: `fx – p1 – d1 – p2 – d2 – p3 – d3 – p4 – d4`.
- `fx` (fixation) and `d1-d4` (delays): Gray screen with fixation dot.
- Slots `p1-p4`: Visual stimuli (family A, B, or R) or unexpected omission (X).
- Omission slots (minimum slot 2) produce three consecutive empty periods: pre-omission delay, omitted slot, post-omission delay.

### 2. Electrophysiological Recording & Laminar Alignment
- Multi-area linear microelectrode arrays spanning 6 canonical cortical regions: V1, V2, MT, MST, FEF, PFC across 3 macaque subjects (C31o, V182o, V198o).
- LFP preprocessed at 1000 Hz, artifact-repaired via robust z-scoring against cross-trial medians.
- Laminar alignment via vFLIP2 crossover between alpha/beta deep and gamma superficial power.

### 3. Spiking Unit Census & Information Decoding (F04)
- Units screened under S1 paired fire-probability inclusion criteria against other-epoch nulls.
- Omission identity decoding evaluated under strict leave-one-temporal-cycle-out (LOCO) cross-validation with within-cycle permutation nulls.
- Evaluated across binary linear SVM (balanced accuracy) and 3-way multinomial logistic regression (log-loss). Both confirm null omission identity decodability.

### 4. LFP Field Dynamics & Hierarchical Modeling (F05)
- Time-frequency representations extracted using multi-taper / Morlet wavelets across 5 canonical bands: theta (4-8 Hz), alpha (8-14 Hz), beta (15-30 Hz), low-gamma (30-50 Hz), high-gamma (50-90 Hz).
- Power normalized to pre-trial baseline via $10 \log_{10}(P / P_{\\text{base}})$.
- Hierarchical Mixed-Effects Models (GLMM Models A through F) quantify area and subject-specific field reorganization.

### 5. Matched SPK-LFP Response Concordance & Dissociation (F06)
- Evaluated on 31 matched session x area biological cells across 15 sessions.
- Direct interaction model: $z_L = \\beta_0 + \\beta_1 z_S + \\beta_2 C + \\beta_3 (z_S \\times C) + \\epsilon$, where $C \\in \\{\\text{OB, OS}\\}$.
- Validated via cluster-robust session-level inference, leave-one-session-out jackknife (15/15 sign consistency), and session-cluster bootstrapping ($B=2000$).

### 6. Multimodal Informational Complementarity (F07)
- Evaluated on single-trial spiking counts and 5-band LFP log-powers for omission (RXRR) vs present stimulus (RRRR) discrimination ($Z_{07}$).
- Compared marginal models $M_S, M_L$ against joint multimodal model $M_{SL}$ under identical 5-fold stratified CV.
- Incremental predictive performance $\\Delta_L = \\text{AUC}(M_{SL}) - \\text{AUC}(M_S)$ and $\\Delta_S = \\text{AUC}(M_{SL}) - \\text{AUC}(M_L)$ verified against conditional permutation nulls and PCA-matched dimensionality controls.
"""
    sections.append(methods_summary)
    
    methods_file.write_text("\n".join(sections), encoding="utf-8")
    print(f"Compiled contexts-methods.md at {methods_file}")


def rebalance_outputs_root():
    """Groups existing 50+ output folders into the 7 designated top-level folders."""
    mapping = {
        # Classification
        "decoding": CLASSIFICATION,
        "condition_spike_trials": CLASSIFICATION,
        
        # Substrates
        "f06_substrate": SUBSTRATES,
        "f07_substrate": SUBSTRATES,
        
        # LFP Dynamics
        "artifact_qc": LFP_DYNAMICS,
        "condition_band_power_trials": LFP_DYNAMICS,
        "condition_tfr_maps_p1d1p2d2p3": LFP_DYNAMICS,
        "condition_tfr_maps_p1d1p2d2p3_v2": LFP_DYNAMICS,
        "condition_tfr_maps_p1d1p2d2p3_v3": LFP_DYNAMICS,
        "fig04_glmm_all_areas_timeresolved": LFP_DYNAMICS,
        "fig04_glmm_all_areas_timeresolved_v2": LFP_DYNAMICS,
        "fig04_glmm_all_areas_timeresolved_v3": LFP_DYNAMICS,
        "lfp_artifact_repair": LFP_DYNAMICS,
        "lfp_band_census": LFP_DYNAMICS,
        "lfp_band_census_stim": LFP_DYNAMICS,
        "lfp_band_census_v2": LFP_DYNAMICS,
        "omission_aligned_tfr": LFP_DYNAMICS,
        "omission_tfr_maps": LFP_DYNAMICS,
        "omission_tfr_maps_final": LFP_DYNAMICS,
        "omission_tfr_maps_ratio": LFP_DYNAMICS,
        "omission_tfr_maps_w1500": LFP_DYNAMICS,
        "qc_lfp_artifacts": LFP_DYNAMICS,
        "stimulus_pooled_tfr_maps_w1500": LFP_DYNAMICS,
        
        # Connectivity
        "channel_area_vector": CONNECTIVITY,
        "complete_omission_network_analysis": CONNECTIVITY,
        "connectivity": CONNECTIVITY,
        "lfp_coupling_matrices": CONNECTIVITY,
        "lfp_lfp_granger_network": CONNECTIVITY,
        "lfp_lfp_te_network": CONNECTIVITY,
        "population_firing_lfp_power_corr": CONNECTIVITY,
        "population_spk_spk_lag_corr": CONNECTIVITY,
        "population_spk_spk_rateratio_nb": CONNECTIVITY,
        "q1_spectral_networks": CONNECTIVITY,
        "q2_spike_networks": CONNECTIVITY,
        "q3_lead_analysis": CONNECTIVITY,
        "spectral_network_analysis": CONNECTIVITY,
        "spectral_relations_pipeline": CONNECTIVITY,
        "spike_lfp_coupling": CONNECTIVITY,
        "spk_spk_granger_network": CONNECTIVITY,
        "within_session_lfp_lfp_sliding_corr": CONNECTIVITY,
        "within_session_spk_lfp_sliding_corr": CONNECTIVITY,
        
        # Exploratory & Legacy
        "diagnostics_fig05": EXPLORATORY,
        "docs": EXPLORATORY,
        "draft": EXPLORATORY,
        "figures": EXPLORATORY,
        "fixlist": EXPLORATORY,
        "jnwb_replications": EXPLORATORY,
        "layers": EXPLORATORY,
        "legacy_root_figures": EXPLORATORY,
        "normalization": EXPLORATORY,
        "publication_figures": EXPLORATORY,
        "publication_visual_review": EXPLORATORY,
        "raster_suites": EXPLORATORY,
        "rasters": EXPLORATORY,
        "relationship_search": EXPLORATORY,
        "visualization_gallery": EXPLORATORY,
    }
    
    target_names = {d.name for d in TARGET_7}
    
    for item in list(OUTPUTS.iterdir()):
        if item.is_dir() and item.name not in target_names:
            dest_parent = mapping.get(item.name, EXPLORATORY)
            dest = dest_parent / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(item), str(dest))
            print(f"Moved {item.name} -> {dest_parent.name}/{item.name}")


def main():
    ensure_dirs()
    
    # 1. Main figures fig01 to fig07
    fig_map = [
        ("01", "fig01_recording_topology_and_paradigm"),
        ("02", "fig02_spiking_exemplar_rasters"),
        ("03", "fig03_unit_census"),
        ("04", "fig04_omission_identity_decoding"),
        ("05", "fig05_v1_area_hierarchy_glmm"),
        ("06", "fig06_v1_pfc_condition_tfr"),
        ("07", "fig07_lfp_spike_coupling"),
    ]
    for fig_num, src_name in fig_map:
        build_figure_folder(fig_num, src_name)
        
    # 2. Supplementary figures sfig01 to sfig33
    build_supplement_folders()
    
    # 3. Manuscript docx package
    copy_manuscript_docx()
    
    # 4. Compiled contexts-methods.md
    compile_contexts_methods()
    
    # 5. Clean up root of outputs/ into exactly the 7 target folders
    rebalance_outputs_root()
    
    # Verify outputs root
    root_dirs = sorted([d.name for d in OUTPUTS.iterdir() if d.is_dir()])
    print(f"\nFinal omission/outputs/ root directories ({len(root_dirs)}):")
    for d in root_dirs:
        print(f"  - {d}")


if __name__ == "__main__":
    main()
