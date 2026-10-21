# Spiking Dynamics

Extract sorted unit spike times, calculate trial-aligned PSTHs with causal exponential
smoothing, fit onset latencies, and compute baseline vs response modulation metrics.

Run the executable tutorial:

```bash
python examples/tutorials/03_spiking.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## The figure

![PSTH of a synthetic unit with a planted response onset and its exponential onset fit](../assets/figures/fig27_spiking_psth_onset.png#only-light)
![PSTH of a synthetic unit with a planted response onset and its exponential onset fit](../assets/figures/fig27_spiking_psth_onset.dark.png#only-dark)

Synthetic, not the tutorial's fixture: Poisson spikes with a planted rate step at 80 ms, smoothed with the same calls the tutorial uses. Panel A is the trial raster; panel B is the PSTH from `jnwb.raster_psth` with the causal smoothing of `jnwb.causal_exp_smooth` and the onset fit of `jnwb.fit_exponential_onset` drawn over it, and the fitted onset and R² in the legend.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/03_spiking.py"
```
