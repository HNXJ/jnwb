# Open Data

Read a public NWB dataset end to end: inspect it, derive its LFP clock from the data, run a PSTH
by cortical layer and LFP band power by depth, check the result, and plot it. The steps apply to
any shared session; the example is one from the Allen Institute OpenScope Global/Local
Oddball project.

Run the executable tutorial:

```bash
python examples/tutorials/09_open_data.py            # renders the figure to a temporary folder
python examples/tutorials/09_open_data.py figures/   # keeps it
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## The data

| | |
|---|---|
| Dataset | DANDI 000253, version 0.240503.0152 |
| DOI | [10.48324/dandi.000253/0.240503.0152](https://doi.org/10.48324/dandi.000253/0.240503.0152) |
| License | [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/): reuse with attribution |
| Session | 1232959154, subject 649323 |
| Units, electrodes, stimuli | `sub-649323_ses-1232959154_ogen.nwb`, asset `81f9bcf2-d0e3-41a4-97e4-6371dafa3e71` |
| Probe B LFP | `sub-649323_ses-1232959154_probe-1_ecephys.nwb`, asset `56e98383-75da-4da3-a61d-39b6f814d9e5` |

Cite: Westerberg, J., Durand, S., Cabasco, H., et al. (2024). *Allen Institute Openscope -
Global/Local Oddball project* (Version 0.240503.0152) [Data set]. DANDI archive.
<https://doi.org/10.48324/dandi.000253/0.240503.0152>. The full author list is in
`examples/data/dandi000253_excerpt.provenance.json`.

The two source files are 4.3 GB together. The tutorial reads
`examples/data/dandi000253_excerpt.nwb`, 7.8 MB, cut from them by
`scripts/build_open_data_excerpt.py` without resampling or unit conversion:

| Kept | Extent |
|---|---|
| Electrodes | the 384 contacts of probe B, with their source ids and atlas locations |
| Units | the 297 units whose peak channel is on probe B, with the source's quality metrics |
| Spikes | the first 10 s, stimulus block 1 padded by 1 s (102.5 to 229.1 s), and the last 10 s; each unit's `obs_intervals` names the three windows |
| Stimuli | the 125 grating rows of block 1 |
| LFP | every second cortical (`VISpm`) channel, 10 of 20, as three series: the recording's first and last 10 s, and block 1 |

The provenance file records the asset ids, the SHA-256 of each source as published and as
verified before the build, every window, and the source values the clock depends on. To rebuild
it, download both assets into one folder from
`https://api.dandiarchive.org/api/assets/<asset id>/download/` and run

```bash
python scripts/build_open_data_excerpt.py --source-dir <that folder>
```

The script refuses a file whose size or SHA-256 differs from the published asset.

## Reading a shared file

1. **Inspect before selecting.** `jnwb.inspect` lists every continuous series, interval table
   and units column. Here it reports the LFP container with three series and `rate_hz: None`:
   the file stores per-sample timestamps and no sampling rate.
2. **Read each time axis's values, and its unit label second.** The LFP `timestamps` are
   labeled `seconds` and step by 24 per sample, from 0 to 273 622 056. They are ticks of the
   acquisition clock. Spike times and stimulus times are in seconds on the session clock.
3. **Derive the rate against an independent clock.** Never assume one; rates differ between
   devices, bands and files.
4. **Check the derivation with a second method**, and state the bound it leaves.
5. **Resolve addressing by id.** A unit's `peak_channel_id` is an electrode id, so its location
   is a lookup in the electrodes table.

## Deriving the LFP clock

The excerpt keeps the recording's first and last LFP sample and its first and last spike, so
both spans cover the whole 9121 s session.

| Quantity | How | Value |
|---|---|---|
| Tick step | the one value of `diff(timestamps)` | 24 |
| Tick rate | LFP tick span / probe B spike span | 29 999.968 ticks/s |
| LFP rate | tick rate / tick step | 1249.9987 Hz |
| Sample 0 | the probe's first spike | 3.5692 s |
| Spike-LFP lag | peak of the spike-count x LFP cross-correlation, strongest channel, per segment | +6.4, +6.4, +8.8 ms (start, block, end) |

The source metadata declares 1250 Hz. At that rate the last sample lands 9.7 ms earlier than the
derived clock places it, a drift as large as the bound below.

The cross-correlation places LFP sample 0 at 3.576 to 3.578 s, 6 to 9 ms after the first spike.
The first spike bounds the start of the recording from above; the correlation lag adds the delay
between population spiking and the LFP deflection, which varies with depth. The correlation also
carries a second peak about 20 ms from the first. The two estimates therefore place
sample 0 within **±10 ms**, and the tutorial refuses a clock whose lag in any segment exceeds that
bound. The three lags agree within 2.4 ms across 9000 s, which checks the tick rate as well as
the offset.

The bound is small against the 0.4 s windows the band power uses. It excludes any LFP latency or
spike-LFP timing claim at millisecond resolution from this file.

## Layers

`location` holds atlas labels such as `VISpm4` and `VISpm2/3`, one layer each. The tutorial reads
it by electrode id. `jnwb.map_peak_channel_to_area` keeps `VISpm2/3` whole but still splits a label such as
`VISp6a/b` into two areas, so it is not used here.

## What the tutorial checks

- one tick step across all three LFP series;
- spike-LFP lags within ±10 ms in every segment;
- every PSTH window lies inside each unit's observation intervals, so an unobserved stretch
  cannot read as silence;
- good cortical units fire more 30 to 130 ms after grating onset than in the 100 ms before;
- band power is finite on every channel. It is the trial-averaged 50 to 80 Hz power during the
  grating over that of the gray screen before it, per channel, in decibels taken once
  (`jnwb.aggregate_to_db`, `how="ratio_of_means"`).

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/09_open_data.py"
```
