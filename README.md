# Omission: Unified Single-Unit & Spectral Analysis (`jnwb`)

Research analysis framework for the **Omission** project — hierarchical visual prediction and omission response analysis across cortical visual and prefrontal hierarchies (V1, V2, V3, V4, MT, MST, TEO, FEF, PFC) across recording sessions.

This is an active research codebase. Statistical and decoding APIs include exploratory dual-test reports; treat confirmatory inference (family-wise FDR, nested CV decoding, Granger diagnostics) as work in progress toward publication-grade use.

---

## Repository Structure

- **`jnwb/`** — Unified Python package for NWB-centric omission analysis (session I/O, spectral, spiking, connectivity, decoding, visualization).
- **`tests/`** — Pytest suite for loaders, spectral/spiking pipelines, and statistical engines. Run locally for the current pass count (do not trust hardcoded numbers in docs).
- **`docs/`** — Documentation on overview, NWB structures, methods, and operations.
- **`examples/`** — Step-by-step usage scripts for spiking, TFR, decoding, and spectral causality.
- **`legacy/`** — Archive of legacy context markdowns, obsolete scripts, and old tests.
- **`etude_no_01_gallery.ipynb`** — Interactive showcase notebook for visualization tasks.

---

## Install

```bash
pip install -e ".[test]"
python -m pytest -q
```

Core dependency includes `pynwb`. The `test` extra pulls pytest and the scientific stack used by the advertised suite.

---

## Quick Start

```python
import jnwb as oa

# 1. Load an enriched session
session = oa.read("D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb")

# 2. Extract single units
units_df = session.find_single_units(quality='stable_plus', area='V1')

# 3. Generate a complete raster suite (Spikes, PSTH, ACG)
res = session.raster_suite(unit_id=2.0, condition='AAAB')
res["figure"].savefig("outputs/task_01_raster.png")
```

---

## 📊 The 10 Highlighted Showcases

The interactive [etude_no_01_gallery.ipynb](file:///d:/workspace/omission/etude_no_01_gallery.ipynb) notebook details these 10 core showcases:

### 1. Single Unit Raster Suite
Generates aligned spike rasters, peristimulus time histograms (PSTH), and autocorrelograms (ACG) for individual neurons.
```python
sess.raster_suite(unit_id=2.0)
```

### 2. Multi-Channel Raw LFP Trace Extraction
lazy-reads and plots raw LFP signals for targeted channels (e.g., 44, 47, 50) of Probe B.

### 3. Multi-Channel MUAe Envelope Visualization
lazy-extracts and plots multi-unit activity envelopes for Probe A channels 1 and 127.

### 4. 2D Log-Frequency TFR Spectrogram
Computes and plots baseline-normalized power spectrograms across theta, alpha, beta, and gamma bands.
```python
sess.plot_tfr(area="PFC", condition="AAXB", phase=3)
```

### 5. Multi-Channel TFR Band Traces
Averages TFR power across channels 20–80 and plots time-resolved traces for all 7 canonical bands.

### 6. Noise vs. Signal Quality Auditing
Generates multi-metric tradeoff plots mapping Signal-to-Noise Ratio (SNR) against Firing Rates and Waveform Shapes.
```python
from jnwb import visual_qc as qc
qc.plot_noise_vs_signal(sess._units_df)
```

### 7. Omission Stability Pie Charts
Summarizes unit quality tiers (e.g., Stable-Plus, Unstable) grouped by cortical recording areas.
```python
sess.pie_charts(by_area=True)
```

### 8. Layer-wise Spectrolaminar Motifs
Identifies superficial and deep layer spectral power dynamics across visual hierarchies.
```python
sess.spectrolaminar_motif(area="V4", condition="AAAB")
```

### 9. Multi-Area Spectral Granger & Granger Proxies
Computes directional lead-lag matrices using relative phase differences to establish hierarchical routing.

### 10. Multi-File Batch Processing & Advanced Querying
Performs batch data inventory checks across multiple NWB files, filtering units by layer, depth, and SNR.
```python
oa.units_across_sessions(sessions_list, criteria={'is_stable_plus': True})
```

---

## 🛠️ Built-in Model Context Protocol (MCP) Server

`jnwb` includes an stdio-based MCP server to expose key data analysis capabilities directly to LLMs:
- **`inspect_nwb_file`**: Resolves session-level metadata, areas, and channels.
- **`get_all_units_metadata`**: Outputs the database of sorted units.
- **`prepare_signal_reference`**: Preprocesses trial-aligned LFP and MUAe signals.
- **`add_tool`**: Safely appends new analysis tools dynamically.
