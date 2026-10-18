# P-335: `curate_and_label` against the four criteria (2026-10-17, at 9a6856a1)

Read-only review by a worker; each cited line re-read by the dispatcher.

| Criterion | Verdict | Evidence |
|---|---|---|
| Composable parts | Partial | `detect_bad_channels`, `interpolate_channel_runs`, `evoked_csd_sink`, `fuse_laminar_anchors` and `map_peak_channel_to_layer` are public (`jnwb/__init__.py`) and tested alone; the dense-zone, silent-end, motif, labelling and xFLIP stages live only inside `curate_and_label`, and the labelling stage has no public part |
| Cited defaults | Fail | The motif bands cite Mendoza-Halliday et al. 2024 (`docs/references.md`); the module docstring calls every other default "working values from 25 and 40 um laminar probes in macaque cortex, not values from the literature", and no receipt records them (about 40 default sites, plus `WELCH_NPERSEG`, `CORRELATION_FS_HZ`, `POWER_BAND_HZ`) |
| Micrometres | Pass | Every width, depth and distance parameter and output carries `_um` or says um in its docstring; contact counts are named as contacts |
| No project vocabulary | Pass | "macaque" and the probe pitches in the module docstring describe where the working values came from; no lab, session or paradigm term in code, defaults or tests |

Repaired with this review: the orchestrator's windowed neighbor-correlation step retyped the detector's decimation rule; both now call `_decimated_for_correlation`.

Open, for a ruling: whether the working-value defaults get a calibration receipt (as `vflip` has in `artifacts/benchmarks/calibration/`), get sources, or stay stated as working values; and whether the inner stages become public parts.
