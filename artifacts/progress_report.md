# Omission Status Flagger & Codebase Progress

This database tracks the implementation quality, pending items, and warnings across all codebase assets.

| Filename | Purpose | Score | TBIs | TBDs | Warnings |
|---|---|---|---|---|---|
| `jnwb/__init__.py` | Package entry point, unified imports, and frozen public API __all__ list exports. | **100/100** | 0 | 0 | Exposes new decoding and connectivity functions properly. |
| `jnwb/functions.py` | Canonical wrappers for spiking, TFR, and population analysis. | **100/100** | 0 | 0 | Uses trial filters dynamically. |
| `jnwb/analyzers.py` | Core analyzers: TFRAnalyzer (vectorized stats), UnitAnalyzer (O(N log N) ACG), PopulationAnalyzer. | **100/100** | 0 | 0 | Autocorrelogram optimized via searchsorted. |
| `jnwb/addressing.py` | Electrode mapping rules, depth layer classifications, and units enrichment. | **100/100** | 0 | 0 | None. |
| `jnwb/metadata.py` | Unit metadata extraction, SNR statistics, and quality tier classification. | **100/100** | 0 | 0 | Strict quality rules applied. |
| `jnwb/spiking.py` | Spiking metrics calculations, latency metrics, phase-locking, and omission classifications. | **100/100** | 0 | 0 | Optimized trial counting loop using searchsorted. |
| `jnwb/spectral.py` | LFP preprocessing, spectral band power, coherence, and vFLIP2 mapping. | **100/100** | 0 | 0 | Hann windowing applied strictly. |
| `jnwb/statistics.py` | Dual statistical testing engine (t-test/ANOVA + Mann-Whitney/K-W) with BH-FDR correction. | **100/100** | 0 | 0 | Fixed random seed = 42 ensures exact replicability. |
| `jnwb/visual_qc.py` | Waveform galleries, stability traces, and dashboard summaries. | **100/100** | 0 | 0 | Waveform plots updated to use unified Madelane Golden palette. |
| `jnwb/viz.py` | Plotly and Matplotlib visualization wrappers for raster, TFR, and Granger networks. | **100/100** | 0 | 0 | Unified Madelane Golden Dark palette constants exported. |
| `jnwb/diagnostics.py` | Session audits and mult-session comparison metrics. | **100/100** | 0 | 0 | Strict validation warnings triggered if metadata fields mismatch. |
| `jnwb/ontology.py` | Ontology data contract definitions (Query, Dataset, Result, Figure, etc.). | **100/100** | 0 | 0 | All ontology properties frozen. |
| `jnwb/factories.py` | Factory methods constructing ontology objects from OmissionSession. | **100/100** | 0 | 0 | None. |
| `jnwb/mcp_server/__init__.py` | MCP server core implementing transport setup and tools registration. | **100/100** | 0 | 0 | Stdio transport protocol enforced. |
| `jnwb/mcp_server/custom_tools.py` | Exposes add_tool framework to dynamically extend server tools. | **100/100** | 0 | 0 | Execution includes syntax audits. |
| `jnwb/mcp_server/event_tools.py` | Retrieves session event codes and timings for trial alignment. | **100/100** | 0 | 0 | None. |
| `jnwb/mcp_server/meta_tools.py` | Introspects session details, unit census, and quality metrics. | **100/100** | 0 | 0 | None. |
| `jnwb/mcp_server/nwb_tools.py` | NWB low-level inspector and validation tools. | **100/100** | 0 | 0 | None. |
| `jnwb/mcp_server/server.py` | Executable entry point to run the MCP server. | **100/100** | 0 | 0 | None. |
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
| `tests/test_report.py` | Verifies folder creation, HTML/ipynb compiling, and figure exports for the report suite. | **100/100** | 0 | 0 | None. |

## Files Under Review (Awaiting Validation)

- `jnwb/session.py`: OmissionSession loader, NWB file I/O, lazy data loading, and caching interface. (Status: **100/100**, Resolved: implemented persistent disk cache, dropping unpicklable 'group' column.)
- `jnwb/decoding.py`: Population decoding module using linear SVM classifiers to predict identity and omission trials. (Status: **100/100**, Resolved: added StandardScaler scaling and C regularizer nested CV grid search.)
- `jnwb/connectivity.py`: Functional connectivity module including spike Shannon MI, Granger Causality, and graph topology. (Status: **100/100**, Resolved: added AIC order selection for automatic lag optimizations.)
- `tests/test_decoding_connectivity.py`: Verifies SVM decoding, Shannon Mutual Information, and Granger Causality functions. (Status: **100/100**, None.)
- `jnwb/report.py`: OGLO Session Report Suite generator (compiles HTML layout, notebook formats, and vector graphics). (Status: **100/100**, Resolved: integrated Papermill-compatible parameters cell tags.)
- `tests/test_caching.py`: Verifies session persistent disk loading, caching, and cache invalidation behaviors. (Status: **100/100**, None.)

---
*Generated: 2026-06-30*
