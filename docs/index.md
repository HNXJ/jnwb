# jnwb Documentation

`jnwb` is a generic, dataset-agnostic Python library for high-density electrophysiology, time-frequency analysis, and statistical neuroscience on Neurodata Without Borders (NWB) files.

---

## Table of Contents

```{toctree}
:maxdepth: 2
:numbered:

01_architecture_and_philosophy
02_paths_addressing_metadata
03_representational_similarity_jrsa
04_spectral_analysis_and_tfr
05_artifact_detection_and_repair
06_spikes_psth_and_onset_dynamics
07_statistical_inference_and_nulls
08_directed_connectivity_and_information
09_decoding_and_visual_qc
10_extending_jnwb_and_verification
api
```

---

## Quick Installation

```bash
pip install jnwb
```

### Optional GPU & Acceleration Backends

```bash
pip install "jnwb[torch,gpu]"
```
