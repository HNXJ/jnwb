<p align="center">
  <a href="https://pypi.org/project/jnwb/"><img src="https://img.shields.io/pypi/v/jnwb?color=brightgreen" alt="PyPI"></a>
  <a href="https://jnwb.readthedocs.io/en/latest/"><img src="https://readthedocs.org/projects/jnwb/badge/?version=latest" alt="Docs"></a>
  <a href="https://github.com/HNXJ/jnwb/actions/workflows/workflow.yml"><img src="https://github.com/HNXJ/jnwb/actions/workflows/workflow.yml/badge.svg" alt="CI/CD"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
</p>

# `jnwb`

Dataset-agnostic Python library for Neurodata Without Borders (NWB 2.0+) electrophysiology analysis: session addressing, representational similarity analysis (jRSA), time-frequency representations (TFR), spike onset dynamics, and statistical inference.

**Documentation**: [https://jnwb.readthedocs.io/](https://jnwb.readthedocs.io/) | **Source**: [https://github.com/HNXJ/jnwb](https://github.com/HNXJ/jnwb)

---

## Why `jnwb`

`jnwb` is a toolbox, not a pipeline. It supplies small, composable operations over NWB files,
arrays and metadata tables; it does not impose a workflow.

- **Dataset-agnostic.** Task structure, condition codes and experimental hypotheses stay in your
  own project code, never in the library.
- **Explicit statistical nulls.** Label permutation takes an exchangeability plan
  (`build_permutation_plan`) rather than silently shuffling everything.
- **Signal semantics preserved.** Units, sampling rates, coordinate frames and 0- vs 1-indexing do
  not change across a function boundary.
- **Composable.** Every capability is usable on its own; nothing requires adopting the rest.

---

## Core capabilities

| Area | Representative API |
| --- | --- |
| NWB metadata & addressing | `get_all_units_metadata`, `electrode_inventory`, `enrich_units_dataframe`, `map_peak_channel_to_area`, `classify_layer_from_depth` |
| Spiking | `raster_psth`, `compute_response_metrics`, `causal_exp_smooth`, `fit_exponential_onset`, `phase_locking_index` |
| LFP & spectral | `compute_psd`, `band_power`, `complex_tfr`, `cross_area_coherence`, `imaginary_coherency`, `bipolar_reference`, `laplacian_reference` |
| Statistics | `build_permutation_plan`, `permute_labels`, `shuffle_pvalue_paired`, `shuffle_pvalue_unpaired`, `shuffle_r2_ci` |
| Population analysis | `jrsa`, `nested_cv_linear_svm`, `compute_population_trajectory`, `build_representation_ladder` |
| Connectivity | `granger_causality`, `phase_slope_index`, `transfer_entropy`, `directed_network` |
| Quality control | `channel_correlation_matrix`, `consensus_bad_trials`, `repair_lfp_trials`, `audit_units`, `audit_electrodes` |
| Visualization | `raster_psth`, `setup_vector_graphics`, `save_figure_suite`, `apply_tight_auto_axis` |

---

## Installation

`jnwb` strictly targets **Python 3.12**.

```bash
# Latest release
pip install jnwb

# Exact verified release
pip install jnwb==0.1.0

# With optional GPU and PyTorch backends
pip install "jnwb[torch,gpu]"
```

### Dependencies
Core dependencies: `numpy`, `scipy`, `pandas`, `h5py`, `pynwb`, `hdmf`, `matplotlib`, `scikit-learn`, `statsmodels`, `joblib`.

---

## Quickstart

### 1. NWB in, table out: unit inventory for a session

```python
import jnwb

# One or more NWB 2.0+ session files
units = jnwb.get_all_units_metadata("session.nwb")          # DataFrame, one row per unit
electrodes = jnwb.electrode_inventory("session.nwb")        # DataFrame, one row per electrode

# Attach electrode-derived columns (peak channel -> area, depth -> layer)
units = jnwb.enrich_units_dataframe(units, electrodes)

report = jnwb.audit_units(units)                            # quality-tier census
print(len(units), "units;", report)
```

### 2. Spikes: PSTH Smoothing & Exponential Onset Latency

```python
import numpy as np
import jnwb

rng = np.random.default_rng(42)
spikes = np.sort(rng.uniform(0.0, 10.0, 300))  # Spike timestamps in seconds
events = np.array([1.0, 3.0, 5.0, 7.0])        # Event timestamps in seconds

# Compute binned PSTH and causal exponential smoothing
time_bins, rate_hz, _ = jnwb.raster_psth(spikes, events, win_ms=(-100.0, 400.0), bin_ms=10.0)
smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)

# Fit causality-bounded exponential onset model
fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds=(0.0, 200.0))
print(f"Onset latency t0: {fit['t0']:.1f} ms (R2 = {fit['r2']:.2f}, status: {fit['bound_status']})")
```

### 3. Field Potentials: Complex TFR & Canonical Band Power

```python
import numpy as np
import jnwb

rng = np.random.default_rng(42)
fs = 1000.0                                     # Sampling rate in Hz
lfp_trace = rng.normal(size=1000)                # Continuous LFP signal (1 second)
freqs = np.linspace(10.0, 60.0, 10)              # Frequency coordinates in Hz

# Time-frequency representation via Morlet wavelets
tfr = jnwb.complex_tfr(lfp_trace, fs=fs, freqs=freqs)

# Compute power in canonical frequency bands (e.g. beta: 15-30 Hz)
beta_power = jnwb.band_power(
    lfp_trace,
    sampling_rate=fs,
    freq_range=jnwb.CANONICAL_BANDS["beta"],
    normalize=False
)
print(f"TFR shape: {tfr.shape}, Beta band power: {beta_power:.4f}")
```

---

## Documentation

Full tutorials, 11 scientific topic guides, API reference, and developer invariants are available on [Read the Docs](https://jnwb.readthedocs.io/).

## License

`jnwb` is released under the [MIT License](LICENSE).
