# Unit Quality Example

Measure the quality of five synthetic units on an eight-contact probe, draw their waveforms down
the probe, and see the four outcomes the unit-quality measures route to: a measure executed, a
missing input requested, a result reported as not estimable, and a single-neuron claim declined.

Run the executable notebook:

```bash
jupyter lab examples/notebooks/unit_quality.ipynb
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](install.md#source-checkout), not `pip install jnwb`.

## What it shows

| Step | Calls | Reports |
|---|---|---|
| Waveform measures | `waveform_features`, `waveform_snr`, `waveform_flatness`, `spatial_derivative_sharpness` | Amplitude in uV, duration in ms, SNR, and two flags against cut-offs the notebook states |
| Spike-train measures | `presence_ratio`, `isi_cv`, `refractory_contamination` | Presence over 60 s blocks, interval variation, violations and contamination for a stated refractory period |
| Waveforms down the probe | `visual_qc.plot_unit_waveforms` | Every contact of each unit, with the voltage unit written on the axis |
| Outcomes | the calls above | One input requested, three results reported as NaN, one claim declined |

![Mean waveforms of five made-up units down an eight-contact probe, and presence ratio against refractory contamination per unit](assets/figures/fig30_unit_quality_waveforms.png#only-light)
![Mean waveforms of five made-up units down an eight-contact probe, and presence ratio against refractory contamination per unit](assets/figures/fig30_unit_quality_waveforms.dark.png#only-dark)

Synthetic: five made-up units generated for this figure, not the notebook's units. Unit 2 stops firing after 240 s, unit 3 carries extra spikes from another source, and unit 4 is flat. A is drawn from `jnwb.waveform_features`; B and C from `jnwb.presence_ratio` and `jnwb.refractory_contamination`.

Every unit and spike train is generated in the notebook from a seeded generator, so each number
describes the made-up units alone. A measure reads one unit and keeps or rejects none; the
measures are defined in [Spikes & Onset Dynamics](06_spikes_psth_and_onset_dynamics.md) and
the plots in [Decoding & Unit-Quality Plots](09_decoding_and_visual_qc.md).
