# Quickstart

A tour of jnwb on NWB 2.0+ electrophysiology. Every operation takes arrays or NWB structures and assumes no particular experiment.

> Documentation tracks the `dev` branch public contract.

## NWB file workflow (start here)

For a new session, use the [Tutorials](tutorials/01_nwb_basics.md) sequence:

0. [Your own NWB file](tutorials/00_your_own_file.md) — discover the layout of a file you did not write.
1. [`jnwb.inspect`](tutorials/01_nwb_basics.md) — list interval tables and columns (no default table).
2. [`jnwb.events` / `jnwb.event_onsets`](tutorials/02_addressing_and_metadata.md) — select opaque event codes; onsets in **seconds**. `codes` is jnwb's default column name, not an NWB one, so pass `code_column=` with whatever `inspect` reported.
3. [Spiking dynamics](tutorials/03_spiking.md) with `unit_spike_times`, `raster_psth`, `causal_exp_smooth`.
4. [LFP and spectral](tutorials/04_lfp_and_spectral.md) with `acquisition_channel`, `epoch_continuous`, `compute_psd`, `wpli`.
5. [Statistics](tutorials/05_statistics.md), [Laminar](tutorials/06_laminar.md), [Ensembles](tutorials/07_ensembles.md), and [End-to-End Workflow](tutorials/08_end_to_end_pipeline.md).

Run locally: `python examples/tutorials/00_your_own_file.py` (add your own file path as an argument), then `01_nwb_basics.py` and `02`–`08`. `examples/` ships in neither the wheel nor the sdist, so these need a [clone](install.md#source-checkout), not `pip install jnwb`.

## Install & Import

```bash
pip install jnwb
```

```python
import jnwb
import numpy as np
```

## Which operation should I use?

| Goal | Primary entry points | Method | Output type |
|------|---------------------|------------------------|-------------|
| **Trial QC & cleaning** | `jnwb.repair_lfp_trials`, `jnwb.bad_channels_from_correlation` | artifact repair + detection | `tuple`, masks |
| **Spectral dynamics** | `jnwb.complex_tfr`, `jnwb.compute_multitaper_psd` | TFR + PSD | `ComplexTFR`, arrays |
| **Directed interaction** | `jnwb.phase_slope_index`, `jnwb.granger` | PSI, Granger | `DirectedResult` |
| **Spiking & latencies** | `jnwb.raster_psth`, `jnwb.fit_exponential_onset` | PSTH + onset fit | arrays, `dict` |
| **Hypothesis testing** | `jnwb.paired_fire_prob_test`, `jnwb.permute_labels` | paired test + permutation | `dict` |
| **Representational geometry** | `jnwb.jrsa` | jRSA | `JRSAResult` |

---

## Executable quickstart script (6-panel figure)

`examples/quickstart_jnwb.py` is the authoritative smoke test. Each panel of the figure below is one operation on synthetic data: artifact repair, band power, onset fitting, label permutation, Granger causality and nested-CV decoding.

![jnwb Quickstart Figure](assets/jnwb_quickstart.png#only-light)
![jnwb Quickstart Figure](assets/jnwb_quickstart.dark.png#only-dark)

The figure is committed output from a run of the command below. If a panel disagrees with
what the script prints on your machine, the script is authoritative.

```bash
python examples/quickstart_jnwb.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](install.md#source-checkout), not `pip install jnwb`.

---

## Step-by-step tour

The steps below are a separate walkthrough, not the panels of `examples/quickstart_jnwb.py`; run the script when you need the figure smoke test.

### 1. Artifact Detection & Repair

Detect and interpolate high-amplitude transients across multichannel LFP arrays, leaving unaffected channels and neighboring time windows intact:

```python
rng = np.random.default_rng(0)
n_trials, n_ch, n_t = 40, 8, 600
t = np.arange(n_t)
seg = rng.normal(0, 1, (n_trials, n_ch, n_t))
seg += 2.0 * np.sin(2 * np.pi * 10 * t / 1000.0)

# Inject synchronous transient artifact on specific trials
for trial_idx in [7, 19, 31]:
    seg[trial_idx, :, 300:330] += 40.0

repaired, frac, diag = jnwb.repair_lfp_trials(seg, times_ms=t, z_thresh=6.0)
print(f"Repaired fraction: {frac:.1%}")
```

### 2. Time-Frequency Dynamics (Complex Morlet TFR)

Extract phase and power with single-trial resolution using Morlet wavelets:

```python
freqs = np.linspace(6.0, 45.0, 30)
tfr = jnwb.complex_tfr(repaired[0], fs=1000.0, freqs=freqs, n_cycles=5.0)

print(f"TFR shape (channels, freqs, time): {tfr.shape}")
print(f"Mean raw power: {tfr.power.mean():.4f}")
```

### 3. Directed Interaction (Phase Slope Index)

Phase slope index between two time series, with a surrogate test. For a single trial the surrogate is a circular shift of the second series; with three or more trials it is a trial permutation:

```python
sig_a = rng.normal(size=1000)
sig_b = np.roll(sig_a, 5) + 0.5 * rng.normal(size=1000)

psi = jnwb.phase_slope_index(sig_a, sig_b, fs=1000.0, bands=(8.0, 30.0), n_surrogates=50, rng=0)
print(f"PSI X->Y: {psi.x_to_y:.4f}, p-value: {psi.p_x_to_y:.4f}")
```

### 4. Spiking PSTH & Onset Dynamics

Calculate a PSTH with its standard error and fit a parametric latency model:

```python
spk_times = np.sort(rng.uniform(0, 10, 200))
event_onsets = np.array([1.0, 3.0, 5.0, 7.0])

time_bins, rate, sem = jnwb.raster_psth(spk_times, event_onsets, win_ms=(-100.0, 400.0), bin_ms=10.0)
onset_fit = jnwb.fit_exponential_onset(time_bins, rate, t0_bounds_ms=(0.0, 250.0))
print(f"Estimated latency t0: {onset_fit['t0']:.2f} ms (status: {onset_fit['bound_status']})")
```

### 5. Non-Parametric Statistical Testing

Compare paired binary outcomes per trial. The p-value comes from a sign-flip shuffle of each trial's pair, and the risk-difference interval from a paired bootstrap:

```python
fires_cond_a = np.array([True, True, False, True, False, True, True, False])
fires_cond_b = np.array([False, False, False, True, False, False, False, False])

stat_res = jnwb.paired_fire_prob_test(
    fires_cond_a, fires_cond_b, n_shuffles=500, n_bootstrap=500, rng=rng
)
print(
    f"Risk difference: {stat_res['risk_difference']:.3f}, "
    f"p-value: {stat_res['p_value_fire_shuffle']:.4f}"
)
```

### 6. Joint Representational Similarity (jRSA)

Compare multi-condition activity patterns across modalities, areas, or models:

```python
# Activity tensor: (conditions, channels, time)
X = rng.normal(size=(6, 16, 50))
Y = X + 0.3 * rng.normal(size=(6, 16, 50))

jrsa_res = jnwb.jrsa(X, Y, metric="rsa", stats=True, permutations=100, rng=0)
print(f"jRSA alignment: {jrsa_res.value:.4f}, p-value: {float(jrsa_res.p):.4f}")
```
