# `jnwb`

Dataset-agnostic Python library for NWB (Neurodata Without Borders) electrophysiology analysis:
session I/O, addressing (channel→area, depth→layer), representational similarity analysis (JRSA),
TFR accumulation/compression, generic statistics, and visual QC.

`jnwb` makes no assumptions about task structure, condition codes, or experiment design. For a
worked example of building a full project on top of it — including a task-specific extension
package, scripts, notebooks, and a manuscript pipeline — see [`omission/`](omission/README.md),
this repo's native large-dataset example project.

---

## Install

```bash
pip install -e ".[test]"
```

## Paths — do this first after any drive remap

Repo-internal paths (`REPO_ROOT`, `outputs_dir()`, `artifacts_dir()`) resolve from the package's
own location and always work. External data roots live on a separate volume and are set by
environment variable — see [`jnwb/paths.py`](jnwb/paths.py) for the full list and defaults.

```python
import jnwb
jnwb.paths.describe()   # every root + whether it currently resolves
```

If a root shows `exists: false`, set its env var — do not edit source, and do not write a new
absolute literal into a script.

---

## Quick start

```python
import jnwb

result = jnwb.jrsa(x1, x2, metric='rsa', stats=True)
result.summary()
result.plot()
```

Null construction under an explicit exchangeability scheme — every call must name `scheme`
(`"within_group"` or `"global"`), there is no default, since a bare `rng.permutation(y)` inside
grouped/session-structured decoding is a documented past bug (see `jnwb/permutation.py`):

```python
import numpy as np
rng = np.random.default_rng(0)
null_labels = jnwb.permute_labels(labels, groups=cycle_id, scheme="within_group", rng=rng)
```

Trial-segmented LFP/TFR artifact detection-and-substitution (cross-channel-synchrony detection,
cross-trial-median repair; see `jnwb/artifact_repair.py`):

```python
repaired, frac_flagged, diagnostics = jnwb.repair_lfp_trials(
    segments, times_ms=times_ms, z_thresh=6.0)          # segments: (n_trials, n_channels, n_times)
repaired_power, frac_flagged_by_band = jnwb.repair_band_artifacts(power, freqs)  # per-band TFR
```

Causal PSTH smoothing and causality-bounded exponential onset-latency fit (a forward-only
kernel by design — an acausal/centered smoother would let post-onset activity bias the fitted
onset earlier than the true rise; see `jnwb/onset_fitting.py`):

```python
smoothed = jnwb.causal_exp_smooth(rate, bin_ms=5.0, tau_ms=30.0)
fit = jnwb.fit_exponential_onset(t_ms, smoothed, t0_bounds=(0.0, None))  # fit["t0"], ["tau"], ["r2"]
```

Unit/electrode metadata extraction, QC classification, and census reporting, from a plain list
of NWB paths:

```python
units = jnwb.get_all_units_metadata(nwb_paths)          # -> DataFrame, one row per unit
units = jnwb.classify_unit_quality(units)                # + quality_class, is_valid, issue_flags
census = jnwb.unit_census_report(units, group_by=["area"])
snr_stats = jnwb.get_snr_analysis(units)                 # -> {'pass_rate': ..., 'snr_mean': ...}
```

Generic spectral analysis — band-limited power, cross-area coherence, 1/f tilt, imaginary
coherency (immune to zero-lag volume-conduction mixing by construction), and bipolar/Laplacian
re-referencing (`jnwb/spectral.py`; `CANONICAL_BANDS` is the single-source-of-truth band-edge
default, theta/alpha/beta/low_gamma/high_gamma):

```python
coh = jnwb.cross_area_coherence(v1_lfp, pfc_lfp, sampling_rate=1000.0)
theta_power_db = jnwb.band_power(lfp, 1000.0, jnwb.CANONICAL_BANDS["theta"], baseline=baseline_lfp)
icoh = jnwb.imaginary_coherency(x, y, sampling_rate=1000.0, freq_range=(1, 100))  # icoh_mean, coh_mag_mean
laplacian = jnwb.laplacian_reference(channel_data, channel_order=depth_order)
```

Modality-agnostic directed functional connectivity — Granger causality, spectral (Geweke)
Granger, phase slope index, and transfer entropy all share one `(X, Y, ...)` contract and
return the same `DirectedResult` shape, so LFP traces, binned spike counts, MUAe envelopes, and
band-power time courses go through identical code (`jnwb/connectivity.py`):

```python
rate_a = jnwb.bin_spikes(spike_times_a, window=(-0.5, 1.0), bin_size_ms=10.0, output="rate")
result = jnwb.granger(v1_lfp, pfc_lfp, order="auto")        # or jnwb.phase_slope_index(..., fs=1000.0)
print(result.x_to_y, result.y_to_x, result.net)              # DirectedResult: uniform across estimators
network = jnwb.directed_network({"V1": v1_lfp, "PFC": pfc_lfp}, method="granger")
```

---

## Module map

The public surface is `jnwb/__init__.py` (`__all__`).

| Module | Role |
|---|---|
| `paths.py` | Repo and data root resolution; the only place absolute paths live |
| `addressing.py` | Peak-channel → area mapping, depth → layer classification |
| `ontology.py`, `jrsa.py` | `Dataset`/`AlignedDataset`/`Question`/`Result` objects; unified RSA engine |
| `statistics.py`, `analyzers.py` | `StatisticalAnalysis`, `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer` |
| `tfr_accumulator.py`, `compression.py` | Poolable TFR summary statistics; NWB fp32 compression |
| `trajectory.py`, `gpu_pca.py` | Population trajectories via GPU SVD |
| `visual_qc.py` | Generic visual QC plotting |
| `bilinear.py`, `nam.py`, `permutation.py` | Generic modeling/statistical primitives |
| `artifact_repair.py`, `artifact_detection.py` | Trial-segmented artifact repair (substitution) / detection (exclusion) |
| `onset_fitting.py` | Causal PSTH smoothing; causality-bounded exponential onset-latency fit |
| `metadata.py` | Unit/electrode metadata extraction, QC classification, census reporting |
| `spectral.py` | Band power, cross-area coherence, 1/f tilt, imaginary coherency, bipolar/Laplacian re-referencing; `CANONICAL_BANDS` |
| `connectivity.py` | Mutual information, Granger causality, phase slope index, transfer entropy; uniform `DirectedResult` |
| `mcp_server/` | stdio MCP server: `inspect_nwb`, `get_event_codes_and_timings`, `prepare_signal_reference`, `add_tool` |

Task-specific functionality (condition codes, unit classification, decoding, connectivity,
figure suites) lives in [`omission/jnwb_ext/`](omission/README.md), not here.

---

## MCP server

`jnwb` includes a stdio Model Context Protocol server for NWB inspection from Claude and other
MCP-compatible clients: `inspect_nwb`, `get_event_codes_and_timings`, `prepare_signal_reference`,
`add_tool`. Depends on `mcp`, `h5py`, `pynwb`, `pandas`, `numpy` (installed via `pip install -e .`).

```bash
python -m jnwb.mcp_server
```

```json
{
  "mcpServers": {
    "jnwb-mcp-server": {
      "command": "python",
      "args": ["-m", "jnwb.mcp_server"]
    }
  }
}
```

---

## Repository layout

| Path | Contents |
|---|---|
| `jnwb/` | The library (above) |
| `tests/` | Pytest suite for the generic library — run it, don't trust pass counts in docs |
| `omission/` | The example project built on `jnwb` — see [`omission/README.md`](omission/README.md) |
| `.claude/skills/` | Task-scoped API guides |

---

## Before you change anything

- **`CLAUDE.md`** — repo doctrine: library invariants, footguns, verification checks that caught
  real errors.
- **`omission/.claude/skills/`** — task-scoped API guides (`omission-data`, `omission-signal`,
  `omission-spiking`, `omission-statistics`, `omission-figures`, `manuscript`, `labyrinth`). There
  is no repo-root `.claude/skills/` — `jnwb/` itself has no dedicated skill yet (see
  `numerical-computing` / `biophysical-modeling`, which are general-purpose, not jnwb-specific).
