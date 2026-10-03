# Unit-quality inventory (13-02)

Read at `be3affa1` on lane `lane-q-13-02`, 2026-10-03. Every behaviour below is read from the code
or reproduced by `q1302_probe.py` and `q1302_probe2.py` (lane scratch, run with `PYTHONPATH` on the
lane tree and `jnwb.__file__` asserted under it); the probe id is in brackets. Problem rows are
P-359 to P-366 in `artifacts/problem_stack.md`.

## A. What jnwb computes

"Generic" means the value is a caller-tunable threshold with no study in it; "convention" means it
encodes one corpus's coding or a cut-off that no cited source supports.

| ID | Function, file:line | Signature | Inputs and units | What the code computes | Defaults, and their class |
|---|---|---|---|---|---|
| F1 | `classify_unit_quality`, `jnwb/metadata.py:207` | `(units_df, thresholds=None) -> DataFrame` | any frame; columns named by `thresholds` coerced to numbers; no unit check | for each threshold key present as a column, flags `col<thresh` (strict); class `Good` with no flag, `Fair` with any flag, `Poor` when a `quality` or `snr` flag is set; `is_valid` = no flag. A NaN, a non-numeric label or an absent column raises no flag, so the unit is `Good` [P1-P3] | `{'quality': 1.0, 'snr': 1.0, 'firing_rate': 0.1}` and the rule that `quality`/`snr` make `Poor`: convention, no source cited (P-361); undefined input passes (P-359) |
| F2 | `assign_quality_tier`, `jnwb/metadata.py:574` | `(quality, trial_presence_fraction, snr, presence_threshold=0.98, snr_threshold=0.5) -> Series` | three Series; `quality` a numeric code, presence a fraction 0-1, SNR unitless as supplied | `q==0` -> `mua`; `q==1` and presence > 0.98 and SNR > 0.5 (strict) -> `stable`; every other row, including `q==2`, NaN quality and string labels, -> `unstable` [P5, P6] | the 0/1 code and the 0.98 and 0.5 cut-offs: convention; the docstring's "common Kilosort-curation convention" cites nothing and states `quality>=1`, which the code does not implement (P-360) |
| F3 | `audit_units`, `jnwb/metadata.py:461` | `(units_df) -> Dict` | `spike_times`, `quality`, `snr`, `firing_rate` columns | count of rows with a non-empty spike train; mean/median/std/min/max of numeric `quality`, `good_count` = quality >= 1.0; SNR mean/median/std and `good_count`/`good_rate` at SNR >= 1.0; firing-rate summary. String quality counts the label `good` [P8] | thresholds 1.0 hard-coded, not parameters [P10]: convention (P-361); one-value quality std reported 0.0, a NaN in `spike_times` raises `TypeError` (P-362) |
| F4 | `get_snr_analysis`, `jnwb/metadata.py:329` | `(units_df, snr_threshold=1.0, detail=False) -> Dict` | `snr` column, coerced; unitless as supplied | count, mean, median, std, min, max of non-NaN SNR; `pass_count`/`pass_rate` at SNR >= threshold (inclusive [P12]); per-session `n`, mean, pass rate when `detail`. All-NaN SNR gives `pass_rate` NaN, `pass_count` 0 [P11]; absent column returns `{}` with a log warning | `snr_threshold=1.0`: a caller parameter, value unsourced (P-361); the docstring example says "SNR>1.0" for an inclusive test (P-364) |
| F5 | `unit_census_report`, `jnwb/metadata.py:262` | `(units_df, group_by=None) -> DataFrame` | the frame `get_all_units_metadata` builds | groupby (default `session_id`, `area`, `depth_class`) counting `unit_id`, and mean/median/std of `firing_rate`, mean/median of `waveform_duration` and `snr`, rounded to 2 decimals; no grouping column -> `describe()`; absent `waveform_duration` raises `KeyError` [P13], as the skill row states | generic; the duration column's unit is not read or reported (P-365) |
| F6 | `plot_unit_waveforms`, `jnwb/visual_qc.py:35` | `(unit_ids, waveforms_dict, max_units_per_page=12, figsize=(16, 10)) -> List[Figure]` | dict of `(n_spikes, n_samples)` or 1-D arrays; no `fs`, no unit | 2-D input: mean and ±1 SD across axis 0; 1-D: the trace. A `(n_channels, n_samples)` template is averaged across channels (-100 on one of 4 channels plots as -25) [P17]; an id absent from the dict gives an empty panel titled with the id | y-axis fixed "Voltage (μV)", x-axis samples: the unit is asserted, not read (P-365) |
| F7 | `plot_unit_quality_distribution`, `jnwb/visual_qc.py:106` | `(units_df, session_ids=None, figsize=(14, 8)) -> Figure` | `firing_rate`, `snr`, `waveform_duration`, `quality`, `area`, `is_stable`/`stable_plus` | histograms of the four metrics, quality per area (jitter from a fixed `default_rng(42)`, visual only), stability bar counts with `<NA>` counted apart. String quality plots an empty histogram, `n=0` [P18] | guide lines at SNR 1.0 and quality 1.0 hard-coded (P-361); "Waveform Duration (μs)" asserted [P18b] while the repository's own fixtures pass ms-scale values (P-365) |
| F8 | `compare_session_quality`, `jnwb/visual_qc.py:276` | `(sessions_comparison_df, figsize=(14, 6)) -> Figure` | one row per session: `session_id`, `snr_mean`, `total_units`, optional `snr_good_rate` (fraction) | bars of mean SNR coloured green > 1.0, orange > 0.5, else red; unit counts; pass rate ×100 coloured > 50 / > 25 | colour cut-offs 1.0, 0.5, 50 %, 25 % hard-coded: convention (P-361); a NaN session is drawn red, as failing [P16]; the pass-rate axis says "SNR > 1.0" whatever threshold produced the rate [P16b] (P-364) |
| F9 | `compare_old_new_criteria` (unexported), `jnwb/metadata.py:612` | `(new_df, old_df, class_col_new, class_col_old, new_key=('session', 'unit_row'), old_key=('session_prefix', 'unit_row_idx')) -> DataFrame` | two frames with a boolean inclusion column each and a two-column join key | left-merges old class onto new by key; `old_screened` = old class non-null; `transition` in `gained`/`lost`/`unchanged_included`/`unchanged_excluded`, an unscreened unit counted `gained` when the new class is true. NaN new class is cast to True (`gained`); a duplicated old key duplicates the new row with conflicting transitions; a matched old row whose class is NaN reads as unscreened [P15] | key defaults name one corpus's columns: convention, B2 (P-363) |
| F10 | `UnitAnalyzer.quality_metrics` (exported class; not named by the item, read because it is the only spike-train quality code), `jnwb/analyzers.py:553` | `(spike_times, waveform_duration_us, firing_rate) -> Dict` | spike times in s, duration in μs, rate in Hz | sorted ISIs; refractory violations at ISI < 2 ms as a percentage; Fano factor over whole 1-s windows; ISI CV; `is_good_single_unit` = violations < 5 % and (Fano NaN or < 2). With 0 or 1 spike: violations 0.0 % and `is_good_single_unit` True [probe 2] | 2 ms, 5 %, Fano 2: hard-coded, unsourced (P-366) |

## B. The downstream criteria

Rows D1 to D9 are **from the recorded description; pending the owner's code**. The description is
the "Context, recorded 2026-10-01" paragraph of `artifacts/todo_stack.md`; the downstream code has
not been made available, so no definition, threshold or channel rule below is read from it.
Classes follow the 13-01 ruling of `artifacts/rulings/2026-10-03.md` (published definitions plus
caller parameters; spatial derivative sharpness and flatness with a required threshold and no
claimed source).

| ID | Criterion | Class | jnwb now | Maps to | Parameter that makes it the caller's choice |
|---|---|---|---|---|---|
| D1 | Peak-channel derivative sharpness across channels | missing-generic | nothing reads channel geometry or a multichannel template | 13-03 spatial derivative sharpness | its threshold, required, and the channel geometry |
| D2 | Flat-waveform rejection | missing-generic | nothing | 13-03 flatness | its threshold, required |
| D3 | Mirrored-waveform rejection | missing-generic; the meaning of "mirrored" is unconfirmed until the code is read | nothing | 13-03 peak polarity (positive against negative peak on the peak channel) | which polarity the caller rejects |
| D4 | Rejection of a peak-channel waveform that rises more than it falls | missing-generic | nothing | 13-03 asymmetry (positive against negative peak on the peak channel) | the asymmetry cut-off |
| D5 | Presence ratio | missing-generic | F2 consumes a supplied `trial_presence_fraction`; no jnwb function computes one | 13-03 presence ratio over caller-given blocks | the blocks, and the cut-off (F2's `presence_threshold`) |
| D6 | SNR | present for thresholding a supplied SNR (F1, F2, F3, F4); missing-generic for computing one | jnwb reads the sorter's `snr` column and never computes SNR from a waveform | 13-03 SNR (published definition, DOI resolved there) | `snr_threshold` (F2, F4) or `thresholds['snr']` (F1); F3's 1.0 is not a parameter (P-361) |
| D7 | Sorter quality | present | F1 `thresholds['quality']`, F2's `quality` code, `get_all_units_metadata(filter_quality=, quality_threshold=)` | none; the description records the flags as unreliable, so using them is the caller's decision | `thresholds['quality']`, `quality_threshold` |
| D8 | Redefined peak-to-trough duration | study-specific (the redefinition); the published trough-to-peak duration is missing-generic | jnwb passes a supplied `waveform_duration` through (F5, F7) with no unit read (P-365) | 13-03 trough-to-peak duration; the 13-03 docstring names the downstream redefinition against it once its code is read | the duration's sample rate `fs`; the redefinition itself stays downstream |
| D9 | Human curation down the probe | study-specific (a human act; the labels stay downstream, fact B2) | F9 diffs two supplied inclusion columns; nothing fits a screen to labels | 13-04, blocked by the 13-01 ruling | the caller's label column |

## C. Open

| Item | Why open |
|---|---|
| D1 to D9 | read from the recorded description only; 13-02's Stop names the owner's permission to read the code, which has not been given |
| The source of F1, F2 and F3 defaults | none is cited in the code, its docstrings, `skills/jnwb-nwb-data/SKILL.md`, `docs/references.md`, `docs/common_mistakes.md` or `artifacts/rulings/`; filed as P-360 and P-361 |
