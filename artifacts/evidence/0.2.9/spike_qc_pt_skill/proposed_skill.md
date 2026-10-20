---
name: spike-qc-pt-classification-jnwb
description: Python/jnwb version of the GLO lab's single-unit QC and peak-to-trough (PT) spike-width pipeline for Kilosort-sorted NWB data from the GLO / fourGLO laminar monkey recordings. Use for selecting "good" single units, waveform/spike-width or trough-to-peak calculation, narrow- vs broad-spiking or putative inhibitory/excitatory (PT-based) classification, GoodUnits_metrics / final_good_cells_idx / AllUnits_metrics files, running the pipeline on a new animal or dataset in Python, or explaining/defending those methods in a paper or reply to reviewers — even if the user just says "the PT stuff", "putative cell types", "good cells" or "spike QC". The MATLAB original is the skill spike-qc-pt-classification.
---

# Spike QC + PT putative cell types, on jnwb

Proposal for a ruling, not a shipped skill: see `README.md` beside this file.

The pipeline turns every Kilosort unit in a set of NWB sessions into a curated list of single units
with a trough-to-peak (PT) duration, thresholded into narrow-spiking (putative inhibitory) and
broad-spiking (putative excitatory) cells. This version runs in Python on jnwb; the MATLAB
original (skill `spike-qc-pt-classification`, in the lab's `alpha_beta` scripts) stays the reference.

```python
import sys; sys.path.insert(0, "<this skill>/scripts")
import spikeqc as sq
```

Load the `jnwb-qc` and `jnwb-nwb-data` skills alongside this one; their safeguards apply (state every
cut-off with the count it produced; a sorter label is an input, not ground truth; no unit is called
a single neuron from quality measures alone).

## What comes from jnwb, what stays here

| Step | Call | From |
|---|---|---|
| Read NWB | `jnwb.nwb_read_io(path, allow_missing=("session_description",))` inside `sq.collect_units` | jnwb (the fourGLO files lack `session_description`; the waiver is recorded on the file object) |
| A. pool units + waveforms | `units, wf = sq.collect_units(nwb_paths, chan_map_file)` | here: channel-map reorder |
| C. peak traces, polarity, frac | `W = sq.peak_waveforms(wf)` | here: deepest-trough channel, `frac` |
| C. manual Yes/No | MATLAB `spikeqc_manual_curation.m` (original skill) → `good_manual` .mat, read with `scipy.io.loadmat` | MATLAB GUI |
| C. bad-by-eye grids | `jnwb.visual_qc.plot_unit_waveforms(ids, {i: wf[i]}, max_units_per_page=15, channels="peak", voltage_unit=None)` | jnwb |
| C. selection + attrition | `good, report = sq.select_units(units, W, good_manual, bad_by_eye)` | here |
| D. PT | `pt, aligned, peak = sq.compute_pt(W["neg_pk"][good])` | here: ramp PT |
| D. classes | `sq.classify_pt(pt, 0.34, legacy_scale=False)` | here |
| Standard measures | `sq.jnwb_features(wf[good])` = `jnwb.waveform_features` per unit; `jnwb.presence_ratio`, `jnwb.refractory_contamination` for spike-train checks | jnwb |
| Record | `sq.record(statistics, parameters, source_id, operation)` → `jnwb.Result` | jnwb |

jnwb has no function for the corpus rules (deepest-trough channel, `frac`, the ramp PT, the
selection); they are this study's conventions. Two jnwb calls look like substitutes and are not:
- `jnwb.probe_geometry` orders contacts by electrode coordinates. In the fourGLO NWB files the
  electrodes table is already in depth order but `waveform_mean` rows are in acquisition order, so
  only the channel map (`DBCONE128.mat`, `sq.load_channel_map`) reorders waveforms correctly. The
  peak traces, `frac`, polarity and PT do not depend on channel order; only the probe image and
  `mappedPkChID` do.
- `jnwb.waveform_features(...)["trough_to_peak_ms"]` is the Siegle et al. (2021) duration on the
  largest-amplitude channel, with no normalisation or ramp; on the validation dataset it equals
  the ramp PT for a minority of units. Report it as a cross-check, never as "PT".

Indices are 0-based in Python. MATLAB `good_cells_final` and `bad_by_eye` lists are 1-based:
subtract 1 when loading them.

## Steps

### A. Collect
`units, wf = sq.collect_units(files, "<channel_maps>/DBCONE128.mat")` returns one table row per
unit (every `nwb.units` column, `spread` converted to µm, `session_id`, `probe`,
`local_peak_channel` 0-based, `spike_times`) and `wf` `(n_units, 128, 82)` in depth order at
30 kHz. Probes other than 128-channel ones are refused. List files explicitly. Save with a dataset
tag, never over an existing dataset's files.

### C. Curation (what defines "good")
1. `W = sq.peak_waveforms(wf)`: `neg_pk` / `pos_pk` traces on the deepest-trough and largest-peak
   channels, `cell_dir` (1 = negative-going), `frac` = range of the first difference / range of
   the trace, max over the two (low = slow, noise-like deflection).
2. Manual pass: the user runs the MATLAB GUI. Never fill `good_manual` automatically.
3. `good, report = sq.select_units(units, W, good_manual, bad_by_eye)` keeps
   **manual Yes AND frac > 0.25 AND nwb `quality` ≠ 0 AND presence_ratio > 0.8 AND negative-going**,
   minus `bad_by_eye` (0-based rows) from scanning 15-unit grids of the survivors sorted by
   half-width. Show `report` whenever unit counts are reported. `presence_ratio` is the NWB column
   (Kilosort/ecephys); `jnwb.presence_ratio` recomputes it from spike times and blocks the caller
   names, which is a different number.

### D. PT and classification
`pt, aligned, peak = sq.compute_pt(W["neg_pk"][good])`: range-normalise; cut −15…+55 samples
around the trough; subtract a ramp 0→1 over the 56 samples from the trough on; the first local
maximum (left edge of a plateau, as MATLAB `findpeaks`) is the repolarization peak; PT = samples /
30 kHz in ms. The ramp finds a peak on broad waveforms whose repolarization keeps rising, where a
plain argmax after the trough runs to the window edge. NaN when the window leaves the trace or no
maximum exists: report the NaN count.

`sq.classify_pt(pt, 0.34, legacy_scale=False)` gives narrow / broad / undefined; the comparison is
in whole samples, so legacy and corrected scales give the same split at any threshold.

## Known issues — mention these when relevant, they matter for the paper

1. **Saved PT values are 2 samples (0.067 ms) too long** (`peaks = pks(1)+16; PT = (peaks-15)/30`
   in the original D). Splits are unchanged if the threshold moves by the same amount, but any PT
   value quoted in text or figures should come from `legacy=False`. Use `legacy=True` only to
   reproduce existing files.
2. **Thresholds differ across scripts**: 0.4 ms, 0.34 ms, 0.29 ms (`PT_gaussian_fitting.m`) and
   0.3 ms in some plot titles, all on the legacy scale. **The study's paper uses 0.34 ms (legacy
   scale)**: narrow = legacy PT < 0.34 ⇔ corrected PT ≤ 0.267 ms.
3. **The step-A metric thresholds are exploratory only** (FR 0.1–40 Hz, presence > 0.6, ISI viol
   < 0.1, SNR > 0.3, amplitude cutoff < 0.1, spread < 350 µm, repol. slope > 0.1) and not applied
   in the final selection, and most final units fail at least one. If a methods section says units
   were filtered on them, flag it.
4. Positive-going units (`cell_dir == 2`) are excluded, so PT is defined only for trough-first spikes.
5. `bad_by_eye` and `good_manual` are hand-made per dataset and must be redone for a new animal.
6. The `quality` criterion is nonzero = good (MATLAB `logical()`).

## Running on a new dataset
1. List the NWB files; confirm 128-ch DBC probes or supply the right channel map.
2. Step A → save `<tag>` files.
3. Write `wf` to .mat for the MATLAB GUI (user's job) → load `good_manual` → by-eye grids →
   `sq.select_units` → show `report`.
4. Step D with `legacy=False`; plot the PT histogram and trough-aligned `aligned` traces before
   choosing a threshold.
5. Wrap counts and thresholds in `sq.record(...)` so the jnwb version, parameters and source travel
   with them.

## Validation
`python scripts/validate_against_saved.py --processed <dir> --nwb-dir <dir> --chan-map <map.mat>
--bad-by-eye <file>` after any edit. It must print `SELECTION MATCH: True`, `PT LEGACY MATCH: max
abs diff = 0.00e+00`, identical corrected-scale splits at 0.34 and 0.4, and `COLLECT MATCH` with
waveforms and metrics True.
