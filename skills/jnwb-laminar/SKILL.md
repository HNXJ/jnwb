---
name: jnwb-laminar
description: Laminar alignment of linear-probe LFP by the spectrolaminar motif. Tests each probe for the alpha-beta and gamma relative-power motif, aligns grand averages on each probe's crossover with superficial up, and aligns the stimulus-evoked CSD on that crossover.
---

# `jnwb-laminar` — laminar alignment by the spectrolaminar motif

## 1. Trigger
Laminar alignment of linear-probe LFP by the spectrolaminar motif: gamma relative power peaks superficially, alpha-beta deep, and the crossover lies near layer 4 (Mendoza-Halliday et al. 2024). This covers:
- a motif test on each probe, retried on half-probe segments, odd or even channels and median filters across channels before the probe is called noise;
- grand averages of relative power across probes, aligned on each probe's crossover with superficial up;
- a stimulus-evoked current source density (CSD) aligned on the same crossover;
- a CSD that alternates in sign from row to row.

Source: Mendoza-Halliday et al. (2024, *Nature Neuroscience*, doi:10.1038/s41593-023-01554-7) for the motif, and Major et al. (2025, *Nature Neuroscience*, doi:10.1038/s41593-025-02168-x) for vFLIP2, its published estimator; `docs/references.md` states how `vflip` differs from FLIP, vFLIP and vFLIP2.

## 2. Routing

The "Motif, crossover and layers" routing rows live in [`references/motif_crossover_and_layers.md`](references/motif_crossover_and_layers.md).

The "The workflow, step by step" routing rows live in [`references/workflow_step_by_step.md`](references/workflow_step_by_step.md).

- `jnwb.vflip2(psd, freqs, *, contact_spacing, orientation="both", layer4_thickness_mm=None, omega_cut=6.0)`: vFLIP2 (Major et al. 2025), ported from its MATLAB code. Returns `VFlip2Result`: the best window's omega and `accepted`, true when omega exceeds `omega_cut`. Below the cut it returns that window with `accepted=False` and `motif_quality="absent"`.
- `jnwb.vflip2_from_lfp(lfp, fs, *, contact_spacing, orientation="both", layer4_thickness_mm=None, omega_cut=6.0)`: `vflip2` on LFP, with the PSD computed as vFLIP2.m computes it for `raw` (continuous, `(n_channels, n_samples)`, cut into 1 s trials) and `raw_cut` input (`(n_channels, n_samples, n_trials)` or a list of trials). vFLIP2.m labels PSD column k as k Hz, so the bands are those labels.

## 3. Invariants & Safeguards
1. **`support_score` is not vFLIP2's omega.** `VFlipResult.support_score` (`jnwb/laminar/_vflip.py`) is jnwb's own score, with no published source, not the omega of the published vFLIP2 code, so vFLIP2's acceptance tiers never apply to it. Say which estimator placed every anchor.
2. **The parity artifact.** An odd neighboring-channel separation pairs each channel with channels of the other parity. Any gain or offset difference between odd and even channels then enters the CSD as a term that alternates in sign from row to row. A CSD that alternates on all channels, while the odd-only and even-only CSDs are smooth, shows that mismatch and not laminar structure. Report the single-parity CSDs beside the all-channel one, with per-probe odd/even ERP amplitude ratios.
3. **What the code refuses.**
   - Below the support threshold, `vflip` returns `accepted=False` and `crossover_contact=None` (`jnwb/laminar/_vflip.py`).
   - `label_layers` labels every channel `'na'` on a rejected fit (`jnwb/laminar/_labels.py`).
   - Neither function fills in a crossover or a layer.
4. **Advice to the caller on selection.** Choosing the best of several strategies is a selection, and no jnwb function runs a strategy grid. Report every strategy's result for every probe, and never present the pass rate of the chosen strategies as a property of the raw recordings. Do not extrapolate a depth beyond an entry's own channels.
5. **A crossover is a depth on this probe.** Calling it layer 4 is an inference. The earliest-sink check of step 6 tests that inference and drops no entry.
6. **The event, not the code.** The CSD and ERP are aligned to the stimulus itself, so any code-to-stimulus delay is measured before epoching.

## 4. Minimal Workflow
```python
# Input: stochastic synthetic.
import jnwb
import numpy as np

fs, n_ch, pitch_um = 1000.0, 24, 100.0
rng = np.random.default_rng(0)
depth = np.linspace(0.0, 1.0, n_ch)[:, None]  # row 0 superficial
alpha_beta = jnwb.bandpass_filter(rng.normal(size=(n_ch, 20000)), fs, 10.0, 19.0)
gamma = jnwb.bandpass_filter(rng.normal(size=(n_ch, 20000)), fs, 75.0, 150.0)
lfp = 4.0 * depth * alpha_beta + (1.0 - depth) * gamma + 0.05 * rng.normal(size=(n_ch, 20000))

# Step 4: each channel subset is a probe of its own, odd and even at twice the pitch.
crossover_um = {}
for name, first in (("all", None), ("odd", 0), ("even", 1)):
    rows, spacing = (slice(None), pitch_um) if first is None else (slice(first, None, 2), 2 * pitch_um)
    freqs, psd = jnwb.compute_psd(lfp[rows], fs, axis=-1)
    fit = jnwb.vflip(psd, freqs, contact_spacing=spacing, orientation="superficial_to_deep")
    assert fit.accepted
    crossover_um[name] = fit.crossover_depth_um + (first or 0) * pitch_um  # on the full-probe frame
assert max(abs(v - crossover_um["all"]) for v in crossover_um.values()) < 2 * pitch_um

# Step 6: CSD at a separation of n contacts, the three-point stencil on every n-th channel.
n, sigma_s_per_m = 3, 0.3  # sigma is illustrative: state and report the value used
erp = rng.normal(size=(n_ch, 300))
csd = np.full_like(erp, np.nan)
for r in range(n):
    csd[r + n::n][: len(erp[r::n]) - 2] = jnwb.current_source_density_1d(
        erp[r::n], pitch_um=n * pitch_um, conductivity_s_per_m=sigma_s_per_m)
```

## 5. Verification
- On the full-probe frame, the odd and even crossovers of the example lie within one subset spacing (twice the pitch) of the whole probe's. Subsets that disagree by more are reported, not averaged.
- The interleaved CSD equals $-\sigma\,(V_{j-n} - 2V_j + V_{j+n})/h^2$, with $h = n \times$ pitch in meters, on rows `n` to `n_ch - n - 1`. It is NaN on the first and last `n` rows.
- For the parity check, scale the odd channels of a smooth ERP by a constant other than 1. The all-channel CSD at an odd n then zigzags from row to row, while the single-parity CSDs only change scale.
- An aligned grand average keeps the number of entries at each depth.

## 6. Documentation
- [`docs/laminar.md`](../../docs/laminar.md)
- [`docs/10_operation_specifications.md`](../../docs/10_operation_specifications.md)
- [`docs/references.md`](../../docs/references.md)
