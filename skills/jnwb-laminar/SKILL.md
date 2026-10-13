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

Source: Mendoza-Halliday et al. (2024, *Nature Neuroscience*, doi:10.1038/s41593-023-01554-7), in `docs/references.md`, which states how `vflip` differs from the paper's FLIP and vFLIP.

## 2. Routing

### Motif, crossover and layers
- `jnwb.vflip(psd, freqs, *, band_low=(8.0, 30.0), band_high=(50.0, 150.0), min_support_score=3.75, device="cpu", depth_axis=None, shallow_end=None)` and `jnwb.vflip_from_lfp(lfp, fs, *, band_low=(8.0, 30.0), band_high=(50.0, 150.0), depth_axis=None, shallow_end=None)`: the frequency-layer inversion depth, from a channels-by-frequency PSD or from a channels-by-time LFP.
  - For finite input, `vflip_from_lfp(lfp, fs)` equals `vflip(psd, freqs)` with `freqs, psd = compute_psd(lfp, fs, axis=-1)`. Note the reversed order and the `axis`.
  - For NaN or Inf input, `compute_psd` raises, while `vflip_from_lfp` returns a result with `accepted=False`.
  - Returns `VFlipResult`. Below the support threshold it returns `accepted=False` and `crossover_contact=None`.
  - `crossover_depth_um` is `crossover_contact` times the contact spacing, the frame `label_layers(depth_range_um=)` uses. With a `probe_geometry`, a `contact_spacing` that disagrees with its `nominal_pitch` raises.
  - `crossover_z_um` is the geometry's absolute z. It is `None` without a geometry whose z varies along the shaft.
  - Without `depth_axis`, depth runs from the table's first row (`depth_anchor="row_order"`). Declare `depth_axis="z"` and `shallow_end="min"` or `"max"` to measure it from the shallow contact whatever the row order (`depth_anchor="shallowest"`).
  - A motif that puts the deep layers at the declared shallow end rejects the fit. The reason reads `rejection_reason="declaration_contradicted"` only when the fit passes every other acceptance test; a weaker fit reports its own reason.
  - A declaration with `orientation="deep_to_superficial"` raises `ValueError` before any fit.
- `jnwb.label_layers(vflip_result, probe_geometry, *, granular_thickness_um=400.0, depth_axis=None, shallow_end=None)`: layer labels relative to a verified crossover contact.
  - Every channel is `'na'` when `vflip_result.accepted` is False: layers are never imputed onto a rejected fit.
  - Pass the same `depth_axis` and `shallow_end` the fit used; a different declaration raises.
- `jnwb.curate_and_label(lfp, fs, *, pitch_um, erp=None, erp_times_ms=None)`: bad-contact detection, short-run interpolation and graded layer labels for epoched LFP `(n_channels, n_epochs, n_samples)`. Every width is in micrometers.
  - Returns `LaminarCurationResult`. Read `grade` before `labels`:
    - A and B carry a laminar claim;
    - C (unstable or inconsistent) and D (vFLIP rejected, motif crossing alone) are sensitivity checks;
    - F sets every label to `"na"`.
  - xFLIP and the evoked CSD are reported as distances to the anchor and never move it. The xFLIP distance is NaN when `xflip.accepted` is False.
  - `band_low_hz` and `band_high_hz` shape the motif profiles, not the vFLIP anchor. Bands must end below `fs / 2`.
  - One cortical sheet is assumed: `n_crossings` above 1 means the shaft needs splitting.
  - The probe, not the contact, is the unit of inference.
- `jnwb.map_peak_channel_to_layer(units_df, curation, channel_ids)`: one curated layer label per unit, from the label of its `peak_channel_id`.
  - `channel_ids` gives the electrode id of each LFP row, in the order passed to `curate_and_label`, and must match `curation.labels` in length.
  - An id that is absent or NaN gets `'na'`. A units table without a `peak_channel_id` column is refused by name.
- The parts of `curate_and_label`:
  - `jnwb.detect_bad_channels(data, fs)`;
  - `jnwb.interpolate_channel_runs(data, bad_mask)`;
  - `jnwb.evoked_csd_sink(erp, times_ms, *, pitch_um)`; the `erp` must be aligned to the stimulus itself;
  - `jnwb.fuse_laminar_anchors()`, which grades an anchor from per-window estimates.

### The workflow, step by step
Each step names the operations it composes. Operations other than the rows above are routed by the skill in brackets. A step with no jnwb operation is caller code, and its rule is stated so it can be written once.

| Step | Rule | Operations |
|---|---|---|
| 1. Events | Align epochs to the stimulus itself, not to its event code. A delay between the code and the stimulus (for example, read from a photodiode) is measured before epoching and is stated with the result. | `events`, `epoch_continuous` (`jnwb-paradigm`) |
| 2. Relative power | Trial-mean PSD per channel, divided at each frequency by its maximum across the probe's channels. This is the published normalization; `vflip` normalizes by the range across contacts instead. | `compute_psd` with `axis=-1` (`jnwb-lfp-spectral`); the division is caller code |
| 3. Motif test | `vflip` accepts a probe when its `support_score` reaches `min_support_score`. The paper's FLIP and vFLIP are other estimators, which jnwb does not compute. | `vflip`, `vflip_from_lfp` |
| 4. Noise strategies | Advice to the caller. A noisy probe can be retried with these choices, the subset taken before the filter:<br>• the whole probe or one half;<br>• all channels, or odd or even ones, at twice the spacing;<br>• a median filter across channels.<br>Fix the grid and the rule that picks a strategy before any result. | `vflip` with `contact_spacing`; `curate_and_label` for bad contacts and short-run interpolation; the median filter is caller code |
| 5. Alignment | The aligned depth of a contact is `crossover_depth_um` minus the contact's own depth from the shallow end, so superficial contacts are positive. `crossover_depth_um` is measured from the shallow end and grows with depth. Declare `depth_axis` and `shallow_end` so the shallow end is the contact the geometry names, whatever the row order. Place entries on one common grid by interpolating inside each entry's own channel range, never beyond it, and report the number of entries at each depth. | `vflip` (`crossover_depth_um`, `depth_axis`, `shallow_end`), `label_layers` |
| 6. Evoked CSD | Start from the trial-mean ERP with each channel's pre-stimulus mean removed. Compute the CSD at a neighbour separation of n contacts of the chosen subset, with h = n times its spacing and a stated tissue conductivity. Use an n for which at least 2n + 3 channels remain. Each CSD row sits at its centre channel and is aligned as in step 5; negative is a sink. The depth of the earliest sink after onset is a check on the crossover, never a selection. | `current_source_density_1d` on every n-th channel, interleaved (`jnwb-lfp-spectral`); `evoked_csd_sink` |

## 3. Invariants & Safeguards
1. **`support_score` is not vFLIP2's omega.** `VFlipResult.support_score` is documented as "Omega" (`jnwb/laminar/_vflip.py`). It is jnwb's own score, not the omega of the published vFLIP2 code, so vFLIP2's acceptance tiers never apply to it. Say which estimator placed every anchor.
2. **The parity artifact.** An odd neighbour separation pairs each channel with channels of the other parity. Any gain or offset difference between odd and even channels then enters the CSD as a term that alternates in sign from row to row. A CSD that alternates on all channels, while the odd-only and even-only CSDs are smooth, shows that mismatch and not laminar structure. Report the single-parity CSDs beside the all-channel one, with per-probe odd/even ERP amplitude ratios.
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
