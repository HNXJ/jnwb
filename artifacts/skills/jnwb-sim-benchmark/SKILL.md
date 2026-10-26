---
name: jnwb-sim-benchmark
description: Synthetic ground-truth generators with planted structure, and the recovery run that tests a method against a planted vFLIP2 crossover. Route here to check that a method recovers what was planted.
---

# `jnwb-sim-benchmark` — synthetic ground truth and recovery runs

## 1. Trigger
Checking whether a method recovers a structure planted in synthetic data: a band-power crossover, a laminar motif, a block correlation, a traveling-wave phase gradient or a group difference. Also building the synthetic NWB file that the executable tutorials read. A recovery count on planted probes says nothing about recorded data; analysis of a recording routes to the skill that owns that analysis.

## 2. Routing

The "Synthetic generators" routing rows live in [`references/synthetic_generators.md`](references/synthetic_generators.md).

The "Recovery runs and receipts" routing rows live in [`references/recovery_runs.md`](references/recovery_runs.md).

## 3. Invariants & Safeguards
1. **The planted values are the ground truth.** A generator returns them, in a receipt (`SynthVFlip2Receipt`, `SynthLaminarReceipt`) or in the arrays it was built from. A method is scored against them, never against its own output.
2. **A seed makes a probe reproducible.** `rng` takes a `numpy.random.Generator` or an integer seed. `None` draws fresh OS entropy, so a probe made without a seed cannot be regenerated.
3. **Draws keep their order.** `synth_vflip2_crossover` draws the background, then the low-band source, then the high-band source. A probe with `snr=0` or `background=False` makes the same draws, so it shares the sources or the background of the probe it is compared with.
4. **A synthetic count names its generator.** Report a recovery count with the generator, its `snr`, the probe count and the seed. One probe is one draw: a single fit can sit several contacts from `z0`, so a recovery claim rests on the counts of the recovery run, not on one fit.
5. **A generator refuses what it cannot plant.** `synth_vflip2_crossover` raises for fewer than 4 contacts, fewer than 64 samples, a sampling rate that puts the 60 to 90 Hz high band at or above Nyquist, a `z0` outside the probe, a bool or float `z0`, a negative `snr` and a non-positive `tau_s`. A refusal is a result: report it, do not substitute another probe.
6. **The oracle is frozen.** `scripts/vflip2_recovery.py --write` freezes `artifacts/evidence/0.2.13/vflip2_oracle.json` once; a later run must reproduce it exactly.

## 4. Minimal Workflow
```python
# Input: stochastic synthetic.
import numpy as np
import jnwb
import jnwb.testing

rng = np.random.default_rng(7)
probe = jnwb.testing.synth_vflip2_crossover(32, 5000, 1000.0, z0=12, snr=4.0, rng=rng)
fit = jnwb.vflip2_from_lfp(probe.lfp, probe.fs, contact_spacing=100.0)
# Compare the fit with the planted contact, and report the fit's own acceptance.
print(fit.accepted, fit.crossover_channel, probe.z0)
```

## 5. Verification
- Every public generator is used by a test. `tests/test_testing_synth.py` names eight of the nine public functions in `jnwb/testing/synth.py`. `synth_vflip2_crossover` is not among them; it is used by `tests/test_vflip2_recovery.py`, `tests/test_vflip2.py`, `tests/test_laminar_curation.py` and `tests/test_vflip2_nuisance.py`.
- The recovery run: `tests/test_vflip2_recovery.py` checks the generator's definitions, the window definition, the frozen oracle and the script's caller path. Its outcomes live in `artifacts/evidence/0.2.13/vflip2_recovery.md`, not in the tests.
- The calibration receipts are checked against a hash of the code they describe; see [`references/recovery_runs.md`](references/recovery_runs.md).

## 6. Documentation
- [`docs/laminar.md`](../../../docs/laminar.md)
- [`docs/references.md`](../../../docs/references.md)
