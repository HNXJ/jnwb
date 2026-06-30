# Omission Status Flagger & Codebase Progress

This database tracks the implementation quality, pending items, and warnings across all codebase assets.

| Filename | Purpose | Score | TBIs | TBDs | Warnings |
|---|---|---|---|---|---|
| `jnwb/session.py` | OmissionSession loader, NWB file I/O, lazy data loading, and caching interface. | **100/100** | 0 | 0 | No warnings. Optimizations for sorting/caching verified by integration tests. |
| `jnwb/functions.py` | Canonical wrappers for spiking, TFR, and population analysis. | **100/100** | 0 | 0 | Uses trial filters dynamically; mock check safety added. |
| `jnwb/analyzers.py` | Core analyzers: TFRAnalyzer (vectorized stats), UnitAnalyzer (O(N log N) ACG), PopulationAnalyzer. | **100/100** | 0 | 0 | Autocorrelogram optimized via searchsorted. |
| `jnwb/addressing.py` | Electrode mapping rules, depth layer classifications, and units enrichment. | **100/100** | 0 | 0 | None. Replaced legacy hardcoded dictionaries. |
| `jnwb/metadata.py` | Unit metadata extraction, SNR statistics, and quality tier classification. | **100/100** | 0 | 0 | Strict quality rules applied for Good/Fair/Poor categorization. |
| `jnwb/spiking.py` | Spiking metrics calculations, latency metrics, and phase-locking index. | **100/100** | 0 | 0 | poisson Rayleigh approximation verified for large sample sizes. |
| `jnwb/spectral.py` | LFP preprocessing, spectral band power, coherence, and vFLIP2 spectrolaminar mapping. | **100/100** | 0 | 0 | Hann windowing applied strictly. |
| `jnwb/statistics.py` | Dual statistical testing engine (t-test/ANOVA + Mann-Whitney/K-W) with BH-FDR correction. | **100/100** | 0 | 0 | Fixed random seed = 42 ensures exact replicability. |
| `jnwb/visual_qc.py` | Waveform galleries, stability traces, and dashboard summaries. | **100/100** | 0 | 0 | Categorical scatter plot jitter added to avoid overlapping dots. |
| `jnwb/viz.py` | Plotly and Matplotlib visualization wrappers for raster, TFR, and Granger networks. | **100/100** | 0 | 0 | Title formatting incorporates units and trial alignments. |
| `jnwb/diagnostics.py` | Session audits and mult-session comparison metrics. | **100/100** | 0 | 0 | Strict validation warnings triggered if metadata fields mismatch. |
| `jnwb/ontology.py` | Ontology data contract definitions (Query, Dataset, Result, Figure, etc.). | **100/100** | 0 | 0 | All ontology properties frozen and immutable. |
| `jnwb/factories.py` | Factory methods constructing ontology objects from OmissionSession. | **100/100** | 0 | 0 | None. |
| `jnwb/mcp_server/__init__.py` | MCP server core implementing inspect_nwb, get_all_units_metadata, prepare_signal_reference. | **100/100** | 0 | 0 | Stdio transport protocol enforced. |
| `jnwb/mcp_server/custom_tools.py` | Exposes add_tool framework to dynamically extend server tools. | **100/100** | 0 | 0 | Execution includes syntax audits to prevent imports injection. |
| `[REF] jnwb/spiking.py` | Refactor and merge `compute_response_metrics` and `classify_omission_response` to optimize trials iteration and minimize loops. | **90/100** | 1 | 0 | Discussion: Decide if we want to run both stimulus and omission classification inside a single trial-loop pass. |
| `[REF] jnwb/visual_qc.py & jnwb/viz.py` | Consolidate overlapping raster and TFR plotting code; unify color palette references under a shared module configuration. | **85/100** | 2 | 1 | Discussion: Decide if Plotly and Matplotlib routines should stay separated or share data-parser methods. |
| `[NEW] jnwb/decoding.py` | New module skeleton to implement population decoding (linear SVM stimulus identity and omission decoding dynamically). | **0/100** | 3 | 2 | Discussion: Need details on SVM hyperparameter tuning options and validation cross-folds configuration. |
| `[NEW] jnwb/connectivity.py` | New module skeleton to house Granger Causality, Mutual Information, and network topology calculations directly inside the package. | **0/100** | 4 | 1 | Discussion: Ensure Granger Wilson factorization fits the precomputed TFR formats. |
| `tests/test_session_coverage.py` | Coverage checks for OmissionSession accessors, properties, and metadata. | **100/100** | 0 | 0 | None. Runs in under 2 seconds. |
| `tests/test_analyzers_coverage.py` | Coverage checks for TFR, Unit, and Population analyzers. | **100/100** | 0 | 0 | None. |
| `tests/test_functions_coverage.py` | Coverage checks for the 20 canonical functions. | **100/100** | 0 | 0 | None. |
| `tests/test_jnwb_core.py` | Verifies data contract immutability and robust statistical NaN/Inf handlers. | **100/100** | 0 | 0 | None. |
| `tests/test_jnwb_integration.py` | End-to-end load-analyze-visualize testing with real data placeholders. | **100/100** | 0 | 0 | None. |
| `tests/test_jnwb_nwb_integration.py` | NWB trial onset and LFP channel query tests. | **100/100** | 0 | 0 | None. |
| `tests/test_mcp_server.py` | Verifies MCP tool registry, syntax warnings, and tool generation. | **100/100** | 0 | 0 | custom_tools path modified to look up relative to workspace root. |
| `docs/omission_overview.md` | Paradigm description, subjects list, arousal/eye metrics overview. | **100/100** | 0 | 0 | None. |
| `docs/nwb_data_structure.md` | Lazy reading guidelines, session maps, probe-area lookup. | **100/100** | 0 | 0 | None. |
| `docs/analysis_methods.md` | Mathematical specs for TFR dB, MMFF Fano Factor, SVM classifications. | **100/100** | 0 | 0 | None. |
| `docs/operations_and_troubleshooting.md` | 15-Step pipeline reference, visual void checks, multi-area sorting rules. | **100/100** | 0 | 0 | None. |
| `README.md` | Quickstart script, project overview, highlights of the 10 showcases. | **100/100** | 0 | 0 | None. |
| `etude_no_01_gallery.ipynb` | 19-cell showcase running all 16 tasks + generalization + batch + unit queries. | **100/100** | 0 | 0 | Contains pre-run figures using actual neural data files. |

---
*Generated: 2026-06-30*
