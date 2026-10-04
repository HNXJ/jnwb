# 09-01 claim table

Lines of the docs prose at `3b280c8a` that are not verbatim at `66477e59` (the 09-01 lane head), 640 of 694 kept verbatim. Each line below was accounted for by the 09-01 verifier: a retitled heading, a retargeted link, a sentence moved to `reading_nwb.md` or `architecture.md`, or reworded text with the same claim. No claim was dropped.

```text
01_architecture_and_philosophy.md:1: # 01. Architecture & Design Philosophy
01_architecture_and_philosophy.md:3: `jnwb` is a Python library for electrophysiology analysis on Neurodata Without Borders (NWB 2.0+) files, written against no particular dataset. This p
01_architecture_and_philosophy.md:7: ## 1. Core Philosophy: Generic Library Core vs. Domain Extensions
01_architecture_and_philosophy.md:9: `jnwb` keeps two things apart:
01_architecture_and_philosophy.md:13: The diagram draws that boundary: only the dashed edge leaves the package.
01_architecture_and_philosophy.md:17: NWB[NWB 2.0+ Files / HDF5 Slabs] --> jnwb[jnwb Generic Core Library]
01_architecture_and_philosophy.md:18: jnwb --> Paths[paths: Root & Volume Resolution]
01_architecture_and_philosophy.md:19: jnwb --> Addr[addressing: Channel -> Area & Depth Class]
01_architecture_and_philosophy.md:20: jnwb --> Meta[metadata: Unit Quality & QC]
01_architecture_and_philosophy.md:21: jnwb --> JRSA[jrsa: Representational Similarity]
01_architecture_and_philosophy.md:22: jnwb --> Spectral[spectral / tfr_accumulator: TFR & Coherence]
01_architecture_and_philosophy.md:23: jnwb --> Conn[connectivity: Granger, PSI, Transfer Entropy]
01_architecture_and_philosophy.md:24: jnwb --> Artifact[artifact_detection / artifact_repair]
01_architecture_and_philosophy.md:25: jnwb --> Spikes[spiking / onset_fitting / trajectory]
01_architecture_and_philosophy.md:26: jnwb --> Stats[statistics / permutation]
01_architecture_and_philosophy.md:27: jnwb --> Decode[decoding: row-wise nested CV SVM, grouped fold builders]
01_architecture_and_philosophy.md:28: jnwb --> Viz[visual_qc / viz: Publication Graphics]
01_architecture_and_philosophy.md:30: jnwb -.->|Consumed by| Ext[Downstream project packages]
01_architecture_and_philosophy.md:33: ### The `jnwb/` Boundary Invariant
01_architecture_and_philosophy.md:35: import `jnwb`. `jnwb` never imports from them, and a regression gate enforces it.
01_architecture_and_philosophy.md:37: ### NWB, PyNWB and HDMF
01_architecture_and_philosophy.md:52: ## 2. Scientific & Epistemic Invariants
01_architecture_and_philosophy.md:54: ### A. Signal Class Independence
01_architecture_and_philosophy.md:58: ### B. Estimand Disambiguation
01_architecture_and_philosophy.md:66: ### C. Causal & Directional Verbs
01_architecture_and_philosophy.md:72: ### D. Mathematical vs. Analysis-Specific Conventions
01_architecture_and_philosophy.md:76: ### E. Unit of Inference & Hierarchical Structure
01_architecture_and_philosophy.md:80: ### F. Valid Nulls & No Synthetic Science
01_architecture_and_philosophy.md:86: ## 3. Module Map & Architecture Summary
02_paths_addressing_metadata.md:1: # 02. Paths, Addressing, Metadata & Ontology
02_paths_addressing_metadata.md:3: Data roots, streaming reads, anatomical addressing (channel $\to$ area, depth $\to$ depth class), unit quality audits and the query ontology.
02_paths_addressing_metadata.md:7: ## 1. Path Management & Drive Remap Isolation (`jnwb/paths.py`)
02_paths_addressing_metadata.md:49: ## 2. Memory-Bounded Array Streaming (`jnwb.io`, `stream_npz_array`)
02_paths_addressing_metadata.md:74: ## 3. Spatial & Laminar Addressing (`jnwb/addressing.py`)
02_paths_addressing_metadata.md:169: association-to-causality step that [Architecture &
02_paths_addressing_metadata.md:170: Philosophy](01_architecture_and_philosophy.md#c-causal-directional-verbs) rules out.
02_paths_addressing_metadata.md:183: ## 4. Unit Metadata, Quality Classification & Census Audits (`jnwb/metadata.py`)
02_paths_addressing_metadata.md:248: ## 5. Query & Event Ontology (`jnwb/ontology.py`)
04_spectral_analysis_and_tfr.md:1: # 04. Spectral Analysis, Coherence & Time-Frequency Representations (TFR)
04_spectral_analysis_and_tfr.md:3: Power spectra, decibel formation, coherence, and Morlet TFRs with streaming accumulation.
04_spectral_analysis_and_tfr.md:192: ## 2. Cross-Area Coherence & Imaginary Coherency
04_spectral_analysis_and_tfr.md:240: ## 3. High-Level Analyzers (`jnwb.analyzers`)
04_spectral_analysis_and_tfr.md:267: ## 4. Complex Morlet Time-Frequency Representations & Accumulation
architecture.md:4: called directly by researchers and composed by AI agents.
architecture.md:96: stay in the project that uses jnwb. The dependency runs one way:
architecture.md:101: J -->|imports| L[NumPy, SciPy, pandas, pynwb]
architecture.md:104: jnwb imports nothing from a project and behaves identically whether one is installed or absent.
architecture.md:105: An operation belongs in jnwb when all five hold:
architecture.md:118: [Philosophy & Boundary](01_architecture_and_philosophy.md) maps the modules, the one-way
architecture.md:119: dependency on downstream projects, and the scientific invariants every operation keeps.
index.md:49: - [Architecture](architecture.md) — the two entry paths, how skills route, and what belongs in jnwb
index.md:50: - [Philosophy & boundary](01_architecture_and_philosophy.md) — scope, units, and dataset independence
index.md:70: <a href="04_spectral_analysis_and_tfr/"><img src="assets/figures/fig05_complex_tfr_coi.png#only-light" alt="Complex TFR with COI" width="100%"></a>
index.md:71: <a href="04_spectral_analysis_and_tfr/"><img src="assets/figures/fig05_complex_tfr_coi.dark.png#only-dark" alt="Complex TFR with COI" width="100%"></a
640 of 694 non-blank lines present verbatim after the change
```
