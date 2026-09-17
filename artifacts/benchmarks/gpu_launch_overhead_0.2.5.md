# GPU launch-overhead receipt (0.2.5, todo 05-45)

Purpose: 05-45 reported that several `device='cuda'` paths were slower than their CPU
siblings, and attributed the cost to per-iteration host/device transfers. The attribution
is wrong. In both paths the cost was **kernel launches** from a Python loop, and the
transfers the item named were the minority of it. This file records what was measured,
what was repaired, and where the remaining CPU/GPU crossover actually sits.

The item's Accept criterion -- "no `device='cuda'` path is slower than its CPU sibling"
-- is **not achievable** for the three Welch-backed entry points at their typical input
sizes, and should not be forced. See "The crossover" below.

## Environment

| Field | Value |
| --- | --- |
| Device | NVIDIA RTX A4000 |
| Driver | 595.95 |
| CUDA runtime | 12090 (12.9) |
| CuPy | 14.0.1 |
| PyTorch | 2.12.0+cu126 |
| Python | 3.14.3 |
| NumPy / SciPy | 2.4.6 / 1.18.0 |
| jnwb | working tree at `c269b7d9` + the 05-45 repair |

**The machine was contended for every number below.** A peer process was running
`scripts/e3_condition_6b.py`, which is not a jnwb script, throughout. Absolute
milliseconds here are therefore not representative performance figures and must not be
quoted as such. Every comparison is instead the paired ratio

> `R = T_cuda / T_cpu`

measured **inside one process**, on identical inputs, with identical warm-up, dtype,
repetition count, estimator settings and `cudaDeviceSynchronize` placement. Where a
"before" and an "after" appear in the same table they were measured in the same process
against each other, not across sessions. `R < 1` means the CUDA route is the faster one.

## 1. `UnitAnalyzer._acg_vectorized`

### What was wrong

Two GPU branches, neither usable at scale:

* **below 30000 spikes** it built the full `N x N` difference matrix. At 29999 spikes --
  just under the threshold the code treated as safe -- that is `29999**2 * 8` bytes =
  **6.71 GiB** of device memory for one autocorrelogram.
* **at or above 30000** it chunked by 1000 and then looped in Python *inside* the chunk.
  At 35000 spikes that is 35001 `cupy.asarray` uploads of a loop-invariant `bin_edges`,
  35000 `cupy.histogram` launches, and 70000 forced device-to-host synchronisations from
  `int(lo[idx])` / `int(hi[idx])`.

Cost split at 35000 spikes: `int(device_scalar)` 2 x 1111.7 ms, `cupy.asarray(bin_edges)`
1574.4 ms, `cupy.histogram` 12161.7 ms. **The launches are 76% of the accounted time; the
transfers 05-45 named are 24%.**

The CPU branch had the same shape -- one `numpy.histogram` per spike.

### The repair

One `_acg_histogram(xp, ...)` serving both devices. Each spike's in-window neighbours are
gathered into one flat index per chunk, so the histogram count is per *chunk*, not per
*spike*. The chunk width comes from the widest window actually present, so the pair budget
is respected on a dense train instead of being latent.

### Measured

| spikes | T_cpu before | T_cuda before | R before | T_cpu after | T_cuda after | R after |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5000 | 129.9 ms | 3.9 ms | **0.030** | 3.1 ms | 2.0 ms | **0.624** |
| 35000 | 935.4 ms | 21797.2 ms | **23.302** | 31.7 ms | 1.9 ms | **0.060** |

`R` rises at 5000 spikes because the CPU side got 41.9x faster while the CUDA side got
1.95x faster -- both devices improved; the ratio moved because the denominator did. At
35000 spikes the CUDA path went from 23x slower than CPU to 17x faster.

### Parity

Counts are bit-identical to the previous CPU loop on both devices, at every size tested:

| spikes | count sum | new CPU == old loop | new CUDA == old loop | old CUDA == old loop |
| ---: | ---: | --- | --- | --- |
| 5000 | 19825 | yes | yes | yes |
| 35000 | 139393 | yes | yes | yes |

## 2. `_welch_csd_gpu`

### What was wrong

Two things, found in that order.

**(a) A Python loop over segments.** One device array appended per segment, then
`cp.stack`. A 16384-sample trace at `nperseg=256` runs 127 iterations and about 762 kernel
launches.

**(b) A duplicated self-spectrum.** `harmonic_analysis`, `spectral_tilt` and `band_power`
all call this helper as `_welch_csd_gpu(trace, trace, ...)` and keep only `pxx`. Half of
the work -- a second transfer, gather, detrend, `rfft`, reduction and copy back -- was a
second computation of the first half, then discarded.

### The repairs

**(a)** One strided index builds every segment at once.

**(b)** A `same_signal = y is x` short circuit reuses the first half. This is exact rather
than approximate: identity means both branches would transfer the same bytes, gather the
same indices and run the same `rfft`, so `Y` is bit-identical to `X` and `conj(X) * Y` is
bit-identical to `conj(X) * X`. `psd_y` is a `.copy()`, not an alias, because the
one-sided scaling below it is in place.

### Measured, n = 16384

`T_cpu` is the `scipy.signal.welch`/`welch`/`csd` triple this helper replaces.

| nperseg | segments | T_cpu | T_cuda before | R before | T_cuda after | R after |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | 127 | 17.18 ms | 25.65 ms | **1.493** | 1.71 ms | **0.100** |
| 1024 | 31 | 6.35 ms | 7.41 ms | **1.167** | 1.63 ms | **0.257** |
| 4096 | 7 | 4.43 ms | 3.18 ms | **0.716** | 1.73 ms | **0.391** |

The self-spectrum short circuit accounts for 0.57-0.60 ms of that at every `nperseg`
tested -- 36% of the call -- taking 1.66 ms to 1.06 ms.

### Parity

28 cases (self and distinct signals x `nperseg` 255/256/1024/4096 x `noverlap`
None/0/64, plus detrend-off and a trace shorter than one segment), four outputs each:
**112 of 112 arrays bit-identical** to the pre-repair implementation.

Against the segment loop specifically, `max|difference| == 0.0` on all four outputs for
`nperseg` 64, 128, 255, 256, 512, 1024 and 2048. At 4096 and 8192 CuPy picks a different
row-mean reduction, the detrend constant moves in its last bits, and the outputs shift by
up to **1.43e-13 relative** (361 and 783 ULPs). That is smaller than this path's
*pre-existing* disagreement with SciPy on the same input, which runs from 2.566e-15 at
`nperseg` 256 to 4.146e-13 at 2048, so the CPU/CUDA gap is not widened.

## 3. The crossover

### The fixed floor

At `nperseg=4096`, what a CUDA call pays before any segment arithmetic:

| component | cost |
| --- | ---: |
| host-to-device of x and y | 0.111 ms |
| window construction | 0.186 ms |
| `rfft` on (7, 4096) | 0.228 ms |
| 4 x device-to-host of the outputs | 0.257 ms |
| sum | 0.782 ms |
| whole strided call | 1.678 ms |

### Where the two devices cross

`R = T_cuda / T_cpu` for the three public entry points, paired, after both repairs:

| samples | seconds @ 1 kHz | harmonic_analysis | spectral_tilt | band_power |
| ---: | ---: | ---: | ---: | ---: |
| 12288 | 12.3 | 1.342 | 1.286 | 1.331 |
| 16384 | 16.4 | 1.183 | 1.133 | 1.144 |
| 18432 | 18.4 | 1.064 | 1.095 | 1.072 |
| 20480 | 20.5 | 1.037 | 1.009 | 1.029 |
| 22528 | 22.5 | **1.009** | **0.973** | **0.986** |
| 24576 | 24.6 | 0.911 | 0.902 | 0.944 |
| 4194304 | 4194.3 | 0.067 | 0.070 | 0.092 |

**The crossover is near 22500 samples.** Before the repairs it sat near 32768.

### Why this is documented and not automated

Below the crossover the workload is intrinsically under GPU break-even: the fixed floor
above is most of a 1.6 ms call, and there is no arithmetic left for it to amortise. No
further rewrite of these functions changes that; only a longer input does.

Routing automatically by input length was considered and **rejected**. The CPU and CUDA
Welch paths do not agree bit for bit (the SciPy disagreement quantified above is
pre-existing and independent of this work), so a size-based switch would make the returned
numbers depend on how long the trace is. That is precisely what `AGENTS.md` invariant 6
forbids -- "Device and worker count never change a number" -- and it is the JNWB-004
failure mode. A documented crossover in each function's `device:` parameter lets the
caller choose with the evidence in front of them, and keeps one number per input.

## Reproducing

Probes are session scratch, not repository files. Every number above is re-derivable from:

* `UnitAnalyzer._acg_vectorized(st, 0.1, 0.001, device=...)` against the pre-repair
  implementation at `c269b7d9`, paired in one process;
* `jnwb.spectral._welch_csd_gpu` against the segment loop reproduced as
  `tests/test_gpu_launch_overhead.py::TestWelchBuildsItsSegmentsInOneIndex._segment_loop_reference`;
* `harmonic_analysis` / `spectral_tilt` / `band_power` with `device='cpu'` and
  `device='cuda'`, warm-up 3, 7 repetitions, median, `cudaDeviceSynchronize` after each
  CUDA repetition.

The shape claims -- histogram count independent of spike count, one `rfft` for a
self-spectrum and two for a pair, one index build per call -- are held by
`tests/test_gpu_launch_overhead.py`, which does not depend on timing.
