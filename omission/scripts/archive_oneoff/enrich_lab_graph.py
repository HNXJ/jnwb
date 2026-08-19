"""Enrich the Labyrinth graph under artifacts/.lab/ with fine-grained nodes for jnwb sub-modules,
analysis pipelines, canonical context files, and the primary Goal node.
"""

import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\nejath\.gemini\antigravity\scratch\labyrinth\clients")
import repo_mapper

TARGET = Path(r"D:\workspace\omission")
PARENT_ID = "omission-jnwb"
ROOT_ID = "labyrinth-omission"

# Connect all top-level scanned folders/docs to ROOT_ID to eliminate loose leaves
TOP_LEVEL_NODES = [
    ("omission-claude", "doc", "CLAUDE.md orientation file", ["CLAUDE.md"]),
    ("omission-examples", "folder", "Example analysis scripts folder", ["examples"]),
    ("omission-legacy", "folder", "Legacy markdown documentation folder", ["legacy"]),
    ("omission-notebooks", "folder", "Suite jupyter notebooks folder", ["notebooks"]),
    ("omission-outputs", "folder", "Generated outputs and figures folder", ["outputs"]),
    ("omission-scripts", "folder", "Publication and pipeline scripts folder", ["scripts"]),
]

SUBMODULES = [
    {
        "id": "jnwb-submodule-core",
        "title": "jnwb.core (Core NWB Loader & Session Engine)",
        "summary": "Handles oa.read(), session caching, NWBHDF5IO lifecycle, and unit quality tiering.",
        "source_paths": ["jnwb/core.py", "jnwb/ontology.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-spiking",
        "title": "omission.jnwb_ext.spiking (Single-Unit Spiking & PSTH)",
        "summary": "UnitAnalyzer, raster plots, PSTH calculations, and omission selectivity metrics.",
        "source_paths": ["jnwb/spiking.py", "jnwb/unit_classification.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-spectral",
        "title": "omission.jnwb_ext.spectral (LFP Spectral & TFR Analysis)",
        "summary": "Multitaper TFR computation, band power extraction, and spectrolaminar (vFLIP2) mapping.",
        "source_paths": ["jnwb/spectral.py", "jnwb/tfr.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-statistics",
        "title": "jnwb.statistics (Dual-Test Parametric/Non-Parametric Stats)",
        "summary": "StatisticalAnalysis object, compare_groups, bootstrap_ci, permutation_test, and FDR correction.",
        "source_paths": ["jnwb/statistics.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-metadata",
        "title": "omission.jnwb_ext.metadata (Grand Unit Table & Metadata Diagnostics)",
        "summary": "Grand unit metadata extraction, classify_unit_quality, unit_census_report, and SNR analysis.",
        "source_paths": ["jnwb/metadata.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-diagnostics",
        "title": "omission.jnwb_ext.diagnostics (Session Audit & Visual QC)",
        "summary": "Session-level auditing, integrity checks, and visual quality control reports.",
        "source_paths": ["jnwb/diagnostics.py", "jnwb/visual_qc.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-population",
        "title": "jnwb.population (Population Dynamics & Summaries)",
        "summary": "PopulationAnalyzer, multi-unit comparisons, population by area, pie charts, and across-session tracking.",
        "source_paths": ["jnwb/population.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-trajectory",
        "title": "jnwb.trajectory (GPU-Accelerated Population Trajectory PCA)",
        "summary": "Time-resolved population spike matrix construction and PyTorch GPU SVD dimensionality reduction.",
        "source_paths": ["jnwb/trajectory.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-jrsa",
        "title": "jnwb.jrsa (Joint Relationship & Spectral Analysis Engine)",
        "summary": "Vectorized 14-metric functional connectivity engine, multi-lag shift, and permutation testing.",
        "source_paths": ["jnwb/jrsa.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-addressing",
        "title": "jnwb.addressing (Channel & Area Mapping Engine)",
        "summary": "Dual-area probe channel resolution (channels 1-64 vs 65-128) and probe-to-area mapping.",
        "source_paths": ["jnwb/addressing.py", "jnwb/sequence_layout.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-decoding",
        "title": "omission.jnwb_ext.decoding (Population State Decoding Engine)",
        "summary": "SVM population classification, stimulus vs omission state decoding, and temporal cross-validation.",
        "source_paths": ["jnwb/decoding.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-connectivity",
        "title": "omission.jnwb_ext.connectivity (Functional Network & Mutual Information Engine)",
        "summary": "Inter-area mutual information, directional Granger causality, and spike-LFP phase coupling networks.",
        "source_paths": ["jnwb/connectivity.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "jnwb-submodule-viz",
        "title": "omission.jnwb_ext.viz (Canonical Visualization & Figure Gallery Engine)",
        "summary": "Madelane Golden Dark palette rendering, Plotly vector layouts, and manuscript figure generation gallery.",
        "source_paths": ["jnwb/viz.py", "jnwb/visual_qc.py"],
        "links": [{"to": PARENT_ID, "relation": "refines"}, {"to": "omission-tests", "relation": "derives_from"}],
    },
    {
        "id": "context-figure3-handout",
        "title": "Context Handout: Figure 3 S+/S-/O+ Selection Methodology",
        "summary": "Template correlation unit selection methodology, 5,000 shuffle permutation test, and exemplar picking notes.",
        "source_paths": ["context/info/09_figure3_handout_2026-07-13.md"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}],
    },
    {
        "id": "context-data-session-readiness",
        "title": "Data Inventory: Session Readiness Catalog",
        "summary": "17 NWB session readiness gates (nwb_ok, sidecar_ok, suite_tfr_ready) governing dataset loads.",
        "source_paths": ["artifacts/data/session_readiness.csv", "artifacts/data/nwb_catalog.json"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-core", "relation": "supports"}],
    },
    {
        "id": "plan-goal-flawless-jnwb",
        "title": "Goal: Flawless jnwb Engine & Pipeline Parity",
        "summary": "Achieve flawless execution, zero silent footguns, and 100% verified analytical parity across jnwb.",
        "source_paths": ["artifacts/developer/plans.json"],
        "links": [{"to": "omission-plan", "relation": "refines"}, {"to": PARENT_ID, "relation": "supports"}],
    },
    {
        "id": "context-concept-laminar-frequency-asymmetry",
        "title": "Scientific Concept: Laminar Frequency Asymmetry (Bastos 2012 / Friston 2010)",
        "summary": "Superficial L2/3 gamma (30-120 Hz) feedforward error vs Deep L5/6 alpha/beta (8-30 Hz) feedback prediction asymmetry.",
        "source_paths": ["jnwb/spectral.py", "jnwb/tfr.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-spectral", "relation": "supports"}],
    },
    {
        "id": "context-concept-twelve-condition-matrix",
        "title": "Scientific Concept: 12-Condition Omission Paradigm Matrix",
        "summary": "12-condition trial design contrasting A-family, B-family, and Random sequences across slots 2, 3, and 4 omissions.",
        "source_paths": ["jnwb/sequence_layout.py", "jnwb/core.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-core", "relation": "supports"}],
    },
    {
        "id": "context-concept-single-unit-selectivity",
        "title": "Scientific Concept: Single-Unit S+/S-/O+ Template Classification (Westerberg 2024)",
        "summary": "9-element firing rate template correlation with 5000-shuffle permutation test for S+, S-, O+, and Null units.",
        "source_paths": ["jnwb/unit_classification.py", "jnwb/spiking.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}],
    },
    {
        "id": "context-concept-spike-lfp-phase-locking",
        "title": "Scientific Concept: Spike-LFP Phase Coupling & PPC (Buffalo 2011 / Fries 2005)",
        "summary": "Spike-field coherence and Pairwise Phase Consistency (PPC) across theta, alpha, beta, and gamma LFP bands.",
        "source_paths": ["jnwb/spiking.py", "jnwb/spectral.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-spectral", "relation": "supports"}],
    },
    {
        "id": "context-concept-parafac-tensor-decomposition",
        "title": "Scientific Concept: PARAFAC 3D Tensor Decomposition (Chao 2018)",
        "summary": "Tensor factorization across Channels x Time-Frequency x Conditions isolating PE1, PE2, and prediction update PE3.",
        "source_paths": ["jnwb/population.py", "jnwb/jrsa.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-jrsa", "relation": "supports"}],
    },
    {
        "id": "context-concept-vip-disinhibitory-ramping",
        "title": "Scientific Concept: VIP Disinhibitory Inter-Stimulus & Omission Ramping (Garrett 2020)",
        "summary": "VIP interneuron ramping during inter-stimulus intervals and stimulus omissions in habituated visual sequences.",
        "source_paths": ["jnwb/spiking.py", "jnwb/population.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}],
    },
    {
        "id": "context-claim-local-oddball-adaptation-release",
        "title": "Empirical Claim: Local Oddball Signaling as Release from Adaptation",
        "summary": "Local oddballs (x-x-x-y) engage >50% of units in L2/3 feedforward stream but do not scale with deviance.",
        "source_paths": ["jnwb/unit_classification.py", "jnwb/spiking.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "context-concept-twelve-condition-matrix", "relation": "supports"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}],
    },
    {
        "id": "context-claim-global-oddball-extragranular-feedback",
        "title": "Empirical Claim: Global Oddball Prediction Error Extragranular Feedback Signature",
        "summary": "Global oddballs (x-x-x-x) emerge sparse (~7-8%) in PFC/AM/PM extragranular layers via feedback propagation.",
        "source_paths": ["jnwb/population.py", "jnwb/jrsa.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "context-concept-laminar-frequency-asymmetry", "relation": "supports"}, {"to": "jnwb-submodule-population", "relation": "supports"}],
    },
    {
        "id": "context-claim-vip-interneuron-omission-ramping",
        "title": "Empirical Claim: VIP Interneuron Pre-Stimulus and Omission Ramping",
        "summary": "L2/3 VIP cells switch to inter-stimulus and omission ramping for familiar images, disinhibiting pyramidal dendrites.",
        "source_paths": ["jnwb/spiking.py", "jnwb/population.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "context-concept-vip-disinhibitory-ramping", "relation": "supports"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}],
    },
    {
        "id": "context-claim-parafac-tri-component-multiplexing",
        "title": "Empirical Claim: PARAFAC 3-Component Multiplexing (PE1, PE2, PE3)",
        "summary": "3D tensor factorization resolves early gamma PE1, late gamma PE2, and late alpha/beta PFC prediction update PE3.",
        "source_paths": ["jnwb/population.py", "jnwb/jrsa.py"],
        "links": [{"to": "omission-context", "relation": "refines"}, {"to": "context-concept-parafac-tensor-decomposition", "relation": "supports"}, {"to": "jnwb-submodule-jrsa", "relation": "supports"}],
    },
    # --- Manuscript Figures (1-10) ---
    {
        "id": "outputs-figure1-paradigm-geometry",
        "title": "Manuscript Figure 1: 12-Condition Omission Paradigm & Probe Geometry",
        "summary": "Visual sequence paradigm, 12-condition matrix, and DBC 128-channel linear probe geometry.",
        "source_paths": ["scripts/build_figure1_paradigm_geometry.py", "outputs/figures/figure_1_paradigm_geometry.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-viz", "relation": "supports"}, {"to": "context-concept-twelve-condition-matrix", "relation": "supports"}],
    },
    {
        "id": "outputs-figure2-single-unit-taxonomy",
        "title": "Manuscript Figure 2: Single-Unit Response Taxonomy & Raster Grid",
        "summary": "Single-unit classification taxonomy (S+, S-, O+, O-, X, Null) and multi-unit raster grid.",
        "source_paths": ["scripts/build_figure2_single_unit_taxonomy.py", "outputs/figures/figure_2_single_unit_taxonomy.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}, {"to": "context-concept-single-unit-selectivity", "relation": "supports"}],
    },
    {
        "id": "outputs-figure3-template-correlation",
        "title": "Manuscript Figure 3: Exemplar Single-Unit Pulse Template Selection",
        "summary": "Template correlation unit selection across 9-element pulse vectors with 5,000-shuffle permutation test.",
        "source_paths": ["scripts/build_figure3_template_correlation.py", "outputs/figures/figure_3_template_correlation.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "context-figure3-handout", "relation": "supports"}, {"to": "jnwb-submodule-spiking", "relation": "supports"}],
    },
    {
        "id": "outputs-figure4-hierarchy-tfr-grid",
        "title": "Manuscript Figure 4: 11-Area Hierarchy TFR Power Spectrogram Grid",
        "summary": "Hierarchy-wide 11-area multitaper TFR spectrogram grid spanning 2-80 Hz over sequence duration.",
        "source_paths": ["scripts/build_figure4_hierarchy_tfr_grid.py", "outputs/figures/figure_4_hierarchy_tfr_grid.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-spectral", "relation": "supports"}, {"to": "context-concept-laminar-frequency-asymmetry", "relation": "supports"}],
    },
    {
        "id": "outputs-figure5-spectral-power-dampening",
        "title": "Manuscript Figure 5: Stimulus vs Omission Spectral Power Dampening Curves",
        "summary": "Grand-average spectral power dampening curves in theta and gamma bands across cortical areas.",
        "source_paths": ["scripts/build_figure5_spectral_power_dampening.py", "outputs/figures/figure_5_spectral_power_dampening.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-spectral", "relation": "supports"}],
    },
    {
        "id": "outputs-figure6-spectrolaminar-vflip",
        "title": "Manuscript Figure 6: Spectrolaminar CSD & vFLIP Alignment Profiles",
        "summary": "CSD sink/source profiles and vFLIP spectrolaminar power alignment across superficial, granular, and deep layers.",
        "source_paths": ["scripts/build_figure6_spectrolaminar_vflip.py", "outputs/figures/figure_6_spectrolaminar_vflip.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-spectral", "relation": "supports"}, {"to": "context-concept-laminar-frequency-asymmetry", "relation": "supports"}],
    },
    {
        "id": "outputs-figure7-area-layer-coherence",
        "title": "Manuscript Figure 7: Pairwise Power Correlation & Imaginary Coherence",
        "summary": "Pairwise area-layer TFR power correlation (r) and imaginary complex coherence Im(C) matrices.",
        "source_paths": ["scripts/build_figure7_area_layer_coherence.py", "outputs/figures/figure_7_area_layer_coherence.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-connectivity", "relation": "supports"}],
    },
    {
        "id": "outputs-figure8-directional-granger",
        "title": "Manuscript Figure 8: Directional Spectral Granger Causality Network Grid",
        "summary": "Directional Granger causality flow networks and VAR model stationarity (ADF) diagnostics.",
        "source_paths": ["scripts/build_figure8_directional_granger.py", "outputs/figures/figure_8_directional_granger.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-connectivity", "relation": "supports"}],
    },
    {
        "id": "outputs-figure9-pfc-population-trajectory",
        "title": "Manuscript Figure 9: PFC Population Trajectory PCA & PyTorch CUDA SVD",
        "summary": "PFC population trajectory state-space PC projections computed via PyTorch CUDA SVD.",
        "source_paths": ["scripts/build_figure9_pfc_population_trajectory.py", "outputs/figures/figure_9_pfc_population_trajectory.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-trajectory", "relation": "supports"}],
    },
    {
        "id": "outputs-figure10-sliding-svm-decoding",
        "title": "Manuscript Figure 10: Sliding-Window SVM Omission Decoding & Pupil Dynamics",
        "summary": "Sliding-window SVM population state decoding accuracy and pupil diameter trajectories.",
        "source_paths": ["scripts/build_figure10_sliding_svm_decoding.py", "outputs/figures/figure_10_sliding_svm_decoding.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-decoding", "relation": "supports"}],
    },
    # --- Supplementary Figures Suite (S1-S8) ---
    {
        "id": "outputs-supplementary-suite",
        "title": "Manuscript Supplementary Figures Suite (S1 - S8)",
        "summary": "Complete 8-panel Supplementary Figures suite covering catalog readiness, unit quality, controls, TFR grids, dampening, CSD, coherence, and diagnostics.",
        "source_paths": ["scripts/build_supplementary_figures.py", "outputs/figures/supplementary/figure_s1_catalog_probe_geometry.svg"],
        "links": [{"to": "omission-outputs", "relation": "refines"}, {"to": "jnwb-submodule-viz", "relation": "supports"}],
    },
    # --- Empirical Facts & Pipeline Constraints ---
    {
        "id": "addressing-fact-dual-area-probe-mapping",
        "title": "Empirical Fact: Dual-Area Probe Channel Resolution Rule",
        "summary": "Probes spanning two areas assign channels 1-64 to area 1 and 65-128 to area 2; resolved via map_peak_channel_to_area.",
        "source_paths": ["jnwb/addressing.py", "jnwb/sequence_layout.py"],
        "links": [{"to": "jnwb-submodule-addressing", "relation": "refines"}, {"to": "jnwb-submodule-core", "relation": "supports"}],
    },
    {
        "id": "core-fact-h5py-bytes-aware-string-decoding",
        "title": "Empirical Fact: Raw h5py Dataset Bytes-Aware String Decoding",
        "summary": "Direct h5py dataset attributes return byte strings (b'2.0') requiring explicit numeric coercion across catalog sessions.",
        "source_paths": ["jnwb/core.py", "jnwb/metadata.py"],
        "links": [{"to": "jnwb-submodule-core", "relation": "refines"}, {"to": "jnwb-submodule-metadata", "relation": "supports"}],
    },
    {
        "id": "spiking-fact-unit-row-position-identity",
        "title": "Empirical Fact: Unit Identity Row-Position Resolution",
        "summary": "OmissionSession.get_spike_times() indexes by raw DataFrame row position (units_df.index), not per-probe Kilosort unit_id.",
        "source_paths": ["jnwb/spiking.py", "jnwb/trajectory.py"],
        "links": [{"to": "jnwb-submodule-spiking", "relation": "refines"}, {"to": "jnwb-submodule-core", "relation": "supports"}],
    },
    {
        "id": "viz-fact-editable-vector-svg-typography",
        "title": "Empirical Fact: Editable Vector SVG Typography Standard",
        "summary": "Enforces plt.rcParams['svg.fonttype'] = 'none' and Arial/Helvetica globally for editable text in Adobe Illustrator.",
        "source_paths": ["jnwb/viz.py", "scripts/build_all_manuscript_figures.py"],
        "links": [{"to": "jnwb-submodule-viz", "relation": "refines"}, {"to": "outputs-supplementary-suite", "relation": "supports"}],
    },
]

def main():
    print(f"Enriching Labyrinth graph under {TARGET}/artifacts/.lab/ ...")
    count = 0

    # 1. Link top-level scanned nodes to root
    for node_id, kind, title, source_paths in TOP_LEVEL_NODES:
        repo_mapper.write_node(
            TARGET,
            node_id=node_id,
            kind=kind,
            title=title,
            summary=f"Top-level {kind} node linked to root.",
            source_paths=source_paths,
            links=[{"to": ROOT_ID, "relation": "refines"}],
        )
        count += 1

    # 2. Add submodule and context nodes
    for item in SUBMODULES:
        repo_mapper.write_node(
            TARGET,
            node_id=item["id"],
            kind="goal" if item["id"] == "plan-goal-flawless-jnwb" else ("submodule" if "submodule" in item["id"] else "context"),
            title=item["title"],
            summary=item["summary"],
            source_paths=item["source_paths"],
            links=item["links"],
        )
        count += 1

    # Re-run analyzer / mapper to update suggestions and global graph state
    res = repo_mapper.analyze(TARGET)
    print(f"Successfully added {count} enriched nodes.")
    print(f"Updated Labyrinth graph status: {res['node_count']} total nodes, {len(res['loose_leaves'])} loose leaves, {len(res['balance_flags'])} balance flags.")

if __name__ == "__main__":
    main()
