<p align="center">
  <img src="https://raw.githubusercontent.com/HNXJ/jnwb/main/docs/assets/jnwb-logo.png" alt="jnwb" width="200">
</p>

<p align="center">
  <a href="https://pypi.org/project/jnwb/"><img src="https://img.shields.io/pypi/v/jnwb?color=brightgreen" alt="PyPI"></a>
  <a href="https://jnwb.readthedocs.io/en/latest/"><img src="https://readthedocs.org/projects/jnwb/badge/?version=latest" alt="Docs"></a>
  <a href="https://github.com/HNXJ/jnwb/actions/workflows/workflow.yml"><img src="https://github.com/HNXJ/jnwb/actions/workflows/workflow.yml/badge.svg" alt="CI/CD"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
</p>

# `jnwb`

Dataset-agnostic Python library for Neurodata Without Borders (NWB 2.0+) electrophysiology: addressing, spikes, LFP, spectral analysis, statistics, population methods, decoding, connectivity, laminar CSD, filtering, QC, and visualization.

**Documentation**: [https://jnwb.readthedocs.io/](https://jnwb.readthedocs.io/) | **Source**: [https://github.com/HNXJ/jnwb](https://github.com/HNXJ/jnwb)

`jnwb` is a toolbox, not a pipeline. It supplies small operations over NWB files, arrays, and metadata tables. Task structure, condition codes, and experimental hypotheses stay in project code.

- **Dataset-agnostic.** No experiment condition names or manuscript results live in the library.
- **Explicit nulls.** Label permutation requires an exchangeability scheme (`global` or `within_group`).
- **Preserved signal semantics.** Units, sampling rates, coordinate frames, and 0- vs 1-indexing do not change across a function boundary.

## Capabilities

| Area | Representative API |
| --- | --- |
| NWB metadata & addressing | `get_all_units_metadata`, `electrode_inventory`, `map_peak_channel_to_area`, `classify_layer_from_depth` |
| Spiking | `raster_psth`, `compute_response_metrics`, `causal_exp_smooth`, `fit_exponential_onset`, `pairwise_phase_consistency` |
| LFP & spectral | `compute_psd`, `compute_multitaper_psd`, `band_power`, `complex_tfr`, `aggregate_to_db`, `current_source_density_1d` |
| Filtering | `bandpass_filter`, `notch_filter` |
| Statistics | `permute_labels`, `cluster_permutation_test`, `shuffle_pvalue_paired`, `paired_fire_prob_test` |
| Population & decoding | `jrsa`, `nested_cv_linear_svm`, `compute_population_trajectory` |
| Connectivity | `granger`, `phase_slope_index`, `transfer_entropy`, `directed_network` |
| Quality control | `channel_correlation_matrix`, `repair_lfp_trials`, `audit_units`, `audit_electrodes` |
| Visualization | `raster_psth`, `setup_vector_graphics`, `save_figure_suite` |

## Installation

Requires Python **3.12 or newer**. Tested in CI on 3.12 and 3.14.

```bash
pip install jnwb
pip install jnwb==0.1.5
pip install "jnwb[torch,gpu]"   # optional
```

Core dependencies: `numpy`, `scipy`, `pandas`, `h5py`, `pynwb`, `hdmf`, `matplotlib`, `scikit-learn`, `statsmodels`, `joblib`.

## Quickstart

```python
import numpy as np
import jnwb

rng = np.random.default_rng(42)
spikes = np.sort(rng.uniform(0.0, 10.0, 300))
events = np.array([1.0, 3.0, 5.0, 7.0])

time_bins, rate_hz, _ = jnwb.raster_psth(spikes, events, win_ms=(-100.0, 400.0), bin_ms=10.0)
smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
fit = jnwb.fit_exponential_onset(time_bins, smooth_hz, t0_bounds=(0.0, 200.0))
print(f"Onset t0: {fit['t0']:.1f} ms (R2={fit['r2']:.2f}, {fit['bound_status']})")

fs = 1000.0
lfp = rng.normal(size=1000)
tfr = jnwb.complex_tfr(lfp, fs=fs, freqs=np.linspace(10.0, 60.0, 10))
beta = jnwb.band_power(lfp, fs=fs, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
print(f"TFR shape: {tfr.shape}, beta power: {beta:.4f}")
```

NWB session inventory:

```python
import jnwb

units = jnwb.get_all_units_metadata("session.nwb")
electrodes = jnwb.electrode_inventory("session.nwb")
units = jnwb.enrich_units_dataframe(units, electrodes)
print(len(units), "units;", jnwb.audit_units(units))
```

## Documentation

Guides, the public API (every symbol in `jnwb.__all__`), and common mistakes are on [Read the Docs](https://jnwb.readthedocs.io/).

## License

MIT. See [LICENSE](LICENSE).
