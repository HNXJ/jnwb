# End-to-End Workflow

A complete workflow demonstrating composition from NWB file inspection, event retrieval,
spiking PSTH calculation, continuous LFP epoching, baseline normalization (decibels last),
connectivity estimation (wPLI), and false discovery rate corrected hypothesis testing.

![PSTH of one synthetic unit by condition, and beta band power before and after condition A onsets, which rises after onset](../assets/figures/fig34_end_to_end_synthetic.png#only-light)
![PSTH of one synthetic unit by condition, and beta band power before and after condition A onsets, which rises after onset](../assets/figures/fig34_end_to_end_synthetic.dark.png#only-dark)

Synthetic, not the tutorial's fixture: a 20 Hz rhythm and a unit with a planted response after condition A onsets, analyzed with the calls of this pipeline (`jnwb.raster_psth`, `jnwb.band_power`). Shading is ±1 SEM.

Run the executable tutorial:

```bash
python examples/tutorials/08_end_to_end_pipeline.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/08_end_to_end_pipeline.py"
```
