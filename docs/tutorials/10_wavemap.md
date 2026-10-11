# WaveMAP

Cluster the mean waveforms of a public dataset's units by shape: align each on its trough,
normalize it, choose a resolution with the sweep of Lee et al. (2021), cluster, and draw the
embedding beside each cluster's mean waveform.

Run the executable tutorial:

```bash
python examples/tutorials/10_wavemap.py            # renders the figure to a temporary folder
python examples/tutorials/10_wavemap.py figures/   # keeps it
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`. `jnwb.wavemap` needs the `wavemap` extra (`pip install jnwb[wavemap]`).

## The data

The units table of the DANDI 000253 excerpt that [Open Data](09_open_data.md) describes:
`units/waveform_mean`, one mean waveform per unit, and `units/id`. The source labels the
waveforms volts; the values read as microvolts, and that reading is unverified. The figure plots
normalized amplitude, so no step depends on the unit.

## The steps

| Step | Call | What it decides |
|---|---|---|
| Align | `jnwb.align_waveforms(raw, fs)` | 12 samples before the trough and 36 after it; a unit whose window leaves the stored samples is dropped |
| Normalize | `jnwb.normalize_waveforms(aligned)` | each row scaled to its trough; a flat row is dropped |
| Choose | `jnwb.wavemap_resolution_sweep(x, resolutions, rng=0)` | the highest mean modularity, rounded to 3 decimals, with every cluster above 20 units in every run; a tie goes to the smaller resolution |
| Cluster | `jnwb.wavemap(x, resolution=..., rng=0)` | Louvain labels on UMAP's nearest-neighbor graph |
| Draw | `jnwb.vis.plot_wavemap(result, aligned)` | panel A the embedding by cluster, panel B each cluster's mean normalized waveform |

The script prints the ids of each cluster's units, so a cluster traces back to the units table.

A cluster is a group of units whose normalized waveforms share a shape at this resolution. It is
not a cell type: the excerpt holds no ground truth for one, and the classifier and SHAP
interpretation of Lee et al. (2021) are not part of this tutorial.
