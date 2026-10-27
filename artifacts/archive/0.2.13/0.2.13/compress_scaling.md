# `compress_fp32` scaling against raw HDF5 (P-344, 2026-10-17)

Probe: `compress_scaling_probe.py`; receipt: `compress_scaling.json` (h5py 3.16.0, HDF5 2.0.0, jnwb at 693ade4e). Each file holds N series of 200 float64 samples; `compress_fp32` casts all N with `verify=False`. The control does the same per-series work in raw h5py: copy the tree, then replace each `data` by a gzip float32 dataset. Medians of 3 runs.

| N | `compress_fp32` (s) | ratio | control (s) | ratio |
|---|---|---|---|---|
| 400 | 1.99 | | 0.26 | |
| 800 | 4.40 | 2.21 | 0.65 | 2.47 |
| 1600 | 10.27 | 2.33 | 1.40 | 2.17 |
| 3200 | 22.04 | 2.15 | 2.79 | 1.99 |

The ratio per doubling (2.15 to 2.33) lies inside the control's (1.99 to 2.47), so raw HDF5 at the same operation count accounts for the slope. `compress_fp32` costs about 8 times the control at every N: it copies the tree twice (structural copy, then compaction) and checks each selected path.
