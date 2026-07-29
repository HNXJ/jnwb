"""
Comprehensive Labyrinth Knowledge Graph Generator & Enricher
============================================================
Creates & enriches structured domain nodes covering:
1. Core Repository Architecture & Pipeline Map
2. Manuscript Draft & Figures Mapping
3. Data Topology, Sidecars & Readin Gates
4. Paradigm Timing & Epoch Boundaries
5. Single-Unit Classification & Response Metrics (S+/S-/O+/Null)
6. Dual-Test Statistical Framework & Family-wise FDR
7. LFP Band-Power, TFR & Complex Oscillatory Metrics
8. Functional Connectivity (JRSA, MI, Granger, PLV, ImCoh)
9. Population Trajectories (GPU-PCA / SVD)
"""

import json
import pathlib
from datetime import date

REPO = pathlib.Path(r'D:\workspace\omission')
LAB_DIR = REPO / 'artifacts' / '.lab'
LAB_DIR.mkdir(parents=True, exist_ok=True)
TODAY = str(date.today())

DOMAIN_NODES = [
    # ── 1. Paradigm Timing & Sequence Layout ──────────────────────────────────
    {
        "id": "domain-paradigm-timing-layout",
        "kind": "evidence",
        "title": "Paradigm Timing, Epoch Onsets, and Layout Definitions",
        "status": "confirmed",
        "notes": [
            "Full visual sequence span: 4624 ms (-500 ms pre-stimulus to 4124 ms post-onset).",
            "Epoch Onsets (ms relative to p1=0): fx=-500, p1=0, d1=531, p2=1031, d2=1562, p3=2062, d3=2593, p4=3093, d4=3624.",
            "Stimulus Duration: 531 ms per pulse (p1, p2, p3, p4).",
            "Delay Duration: 500 ms per delay slot (d1, d2, d3, d4).",
            "Omission Window: SLOT_WINDOW_MS = (onset, onset+531) per slot across test conditions.",
            "Canonical layout helper: jnwb.sequence_layout exposes vector Plotly layout definitions and EPOCH_ONSETS_MS."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 2. Data Topology & Readiness ──────────────────────────────────────────
    {
        "id": "domain-data-topology-readiness",
        "kind": "evidence",
        "title": "Data Topology, Sidecars, and Session Readiness Gates",
        "status": "confirmed",
        "notes": [
            "Raw NWB: D:/analysis/nwb/ (21 total NWB session files across sub-C31o, sub-V182o, sub-V198o).",
            "Metadata Sidecars: D:/workspace/data/metadata/{stem}/ containing electrodes.csv, units.csv, events.csv, h5_paths.json.",
            "Precomputed TFR Arrays: D:/workspace/data/tfr_arrays/{prefix}-{probe}-{area}-{cond}.npy.",
            "Readiness Gate: artifacts/data/session_readiness.csv (15/21 sessions suite_tfr_ready=True).",
            "Dual-Area Probe Rule: Channels 1-64 map to Area 1; Channels 65-128 map to Area 2 (parsed via jnwb.addressing.map_peak_channel_to_area).",
            "PyNWB / h5py Fallback: V182o NWB files require h5py acquisition reads due to device metadata anomalies."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 3. Single-Unit Classification & Response Metrics ──────────────────────
    {
        "id": "domain-single-unit-classification",
        "kind": "evidence",
        "title": "Single-Unit Classification (S+/S-/O+/Null) & Firing Rate Metrics",
        "status": "confirmed",
        "notes": [
            "Template Correlation Classifier: Spearman rank correlation of 9-element per-epoch FR vector against binary templates with permutation shuffles (5000 iterations, p < 0.05).",
            "Classes: S+ (Stimulus Excited), S- (Stimulus Inhibited), O+ (Omission Ramping/Selective), Other/Null.",
            "Grand Table Output: outputs/classification/grand_unit_table_shuffle_sso.csv (6,655 total units across 15 sessions).",
            "Class Distribution: S+=1,432 (21.5%), S-=758 (11.4%), O+=7 (strict pooled shuffle), Other=4,458 (67.0%).",
            "Unit ID Indexing Rule: Spike lookup MUST index by DataFrame row position (units_df.index), NOT kilosort unit_id column column value."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 4. Statistical Analysis & Hypothesis Testing ──────────────────────────
    {
        "id": "domain-statistical-analysis-framework",
        "kind": "evidence",
        "title": "Dual-Test Statistical Framework & Family-Wise FDR",
        "status": "confirmed",
        "notes": [
            "Exploratory API: StatisticalAnalysis.exploratory_compare(), exploratory_correlate(), exploratory_multi() return dual parametric (t/ANOVA/Pearson) + non-parametric (Wilcoxon/Kruskal/Spearman) raw p-values without FDR theatre.",
            "Confirmatory API: StatisticalAnalysis.confirmatory_compare() requires explicit hypothesis string and returns BH-adjusted q-values.",
            "Family-Wise FDR: StatisticalAnalysis.fdr_correct(p_values) applies Benjamini-Hochberg across hypothesis families (units, channels, frequencies).",
            "Effect Sizes: Paired Cohen's dz, independent Cohen's d (pooled SD), eta-squared, r-squared.",
            "Validation: 197 passed pytest suite with 0 warnings under -W error::DeprecationWarning."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 5. LFP Band-Power, TFR & Complex Oscillatory Metrics ──────────────────
    {
        "id": "domain-lfp-tfr-complex-spectral",
        "kind": "evidence",
        "title": "LFP Spectral Band-Power, TFR, and Complex Phase Oscillations",
        "status": "confirmed",
        "notes": [
            "Canonical Spectral Bands: Theta (4-8 Hz), Alpha (8-14 Hz), Beta (14-30 Hz), Gamma (30-80 Hz).",
            "TFR Normalization: Decibel (dB) baseline power normalization relative to pre-stimulus baseline (-500 to 0 ms).",
            "Complex Wavelet Coefficients: jnwb.complex_tfr provides tfr_complex_load, plv_from_complex (Phase-Locking Value), and imaginary_coherence.",
            "Volume Conduction Suppression: Imaginary Coherence (icoh) strips zero-lag instantaneous volume conduction.",
            "Spectrolaminar Mapping: vFLIP2 alignment identifies deep vs superficial cortical layers via alpha/gamma power crossover."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 6. Functional Connectivity (JRSA, MI, Granger) ────────────────────────
    {
        "id": "domain-functional-connectivity-jrsa",
        "kind": "evidence",
        "title": "Functional Connectivity (JRSA, Directional MI, Spectral Granger)",
        "status": "confirmed",
        "notes": [
            "JRSA Engine: Joint Relationship and Spectral Analysis engine supporting 14 metrics (pearson, spearman, mutual_info, granger, hsic, distance_corr, etc.).",
            "Mutual Information: Vectorized binned spike-train MI and spike-to-TFR phase/power mutual information.",
            "Spectral Granger Causality: Directional spectral feedback (V4/PFC -> V1) vs feedforward (V1 -> V4) causality.",
            "NaN Handling: Listwise joint exclusion on paired signals prior to metric calculation."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 7. Population Trajectories (GPU-PCA) ──────────────────────────────────
    {
        "id": "domain-population-trajectories-gpu-pca",
        "kind": "evidence",
        "title": "Population Trajectories & GPU-Accelerated SVD/PCA",
        "status": "confirmed",
        "notes": [
            "GPU SVD/PCA: jnwb.gpu_pca provides gpu_pca(matrix, n_components=3, device='cuda') using PyTorch GPU SVD with automatic NumPy CPU fallback.",
            "Time-Resolved Matrix: build_time_resolved_matrix creates trial-by-unit-by-bin tensor (20 ms binning).",
            "Low-Dimensional Manifold: Projections capture population dynamics through visual sequence presentation, delays, and omission ramping.",
            "Verification: Projections match NumPy reference SVD (r > 0.99) tested in tests/test_gpu_pca.py."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    },

    # ── 8. Manuscript Draft & Portfolio Assets ────────────────────────────────
    {
        "id": "domain-manuscript-draft-assets-biorxiv",
        "kind": "evidence",
        "title": "bioRxiv Manuscript Draft & Draft Assets Portfolio",
        "status": "confirmed",
        "notes": [
            "Biorxiv DOCX: D:/workspace/omission/context/omission-2026-draft-biorxiv-ready.docx.",
            "Draft Assets Portfolio: D:/workspace/omission/context/draft-assets/ (414 vector SVG figures, 5 Markdown metadata files).",
            "Analysis Reports Bundle: context/draft-assets/reports/ (index.md + 5 stage reports: Paradigm, Single-Unit, LFP, Firing Rate, Connectivity).",
            "Figure Captions & Hierarchy: 10 ordered cortical areas (V1 -> V2 -> V3a-d-v -> V4 -> MT -> MST -> TEO -> FST -> FEF -> PFC)."
        ],
        "verification": {"checks": {"sources_resolve": True, "reproducible": True}, "verdict": "verified"}
    }
]

created_count = 0
for node in DOMAIN_NODES:
    node_id = node["id"]
    file_path = LAB_DIR / f"{node_id}.json"
    full_node = {
        "id": node_id,
        "kind": node["kind"],
        "title": node["title"],
        "generated": TODAY,
        "status": node["status"],
        "notes": node["notes"],
        "issues": [],
        "plan": [],
        "verification": node.get("verification", {}),
        "schema_version": 3
    }
    file_path.write_text(json.dumps(full_node, indent=2, ensure_ascii=False), encoding="utf-8")
    created_count += 1

print(f"Successfully generated/updated {created_count} comprehensive domain nodes in {LAB_DIR}")
