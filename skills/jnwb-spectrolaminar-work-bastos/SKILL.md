---
name: jnwb-spectrolaminar-work-bastos
description: SpectrolaminarWork-Bastos, the Bastos lab spectrolaminar workflow that tests each probe for the alpha-beta and gamma relative-power motif under several noise strategies, aligns grand averages on the crossover with superficial up, and aligns the stimulus-evoked CSD on that crossover.
---

# `jnwb-spectrolaminar-work-bastos` — SpectrolaminarWork-Bastos

## 1. Trigger
Laminar alignment of linear-probe LFP by the spectrolaminar motif (gamma relative power peaking superficial, alpha-beta deep, the crossover near layer 4; Mendoza-Halliday et al. 2024): a motif test on each probe, retrying a noisy probe on half-probe segments, odd or even channels and median filters across channels before calling it noise; grand averages of relative power across probes aligned on each probe's crossover with superficial up; a flash-evoked current source density (CSD) aligned on the same crossover, with each session's photodiode delay; a CSD that alternates in sign from row to row.

Sources: the motif and its vFLIP2 code, Mendoza-Halliday et al. (2024, *Nature Neuroscience*, doi:10.1038/s41593-023-01554-7; code on Dryad, doi:10.5061/dryad.9w0vt4bnp); layer 4 placed from the earliest MUA onset, the earliest CSD sink and the spectrolaminar crossing, with a tissue conductivity of 0.4 S/m, Westerberg, Xiong et al. (2024, *Hierarchical substrates of prediction in visual cortical spiking*, bioRxiv, doi:10.1101/2024.10.02.616378).

## 2. Routing

### Motif, crossover and layers
- `jnwb.vflip(psd, freqs, *, band_low=(8.0, 30.0), band_high=(50.0, 150.0), min_support_score=3.75, device="cpu", depth_axis=None, shallow_end=None)` and `jnwb.vflip_from_lfp(lfp, fs, *, band_low=(8.0, 30.0), band_high=(50.0, 150.0), depth_axis=None, shallow_end=None)`: Frequency-layer inversion depth from a channels-by-frequency PSD, or from a channels-by-time LFP. `vflip_from_lfp(lfp, fs)` equals `vflip(psd, freqs)` with `freqs, psd = compute_psd(lfp, fs, axis=-1)` for finite input only: note the reversed order and the `axis`. For NaN or Inf input `compute_psd` raises, while `vflip_from_lfp` returns a result with `accepted=False`. Returns `VFlipResult`; below the support threshold it returns `accepted=False` and `crossover_contact=None`. `crossover_depth_um` is `crossover_contact` times the contact spacing, the frame `label_layers(depth_range_um=)` uses (with a `probe_geometry`, a `contact_spacing` that disagrees with its `nominal_pitch` raises); the geometry's absolute z is `crossover_z_um`, `None` without a geometry whose z varies along the shaft. Without `depth_axis` the depth runs from the table's first row (`depth_anchor="row_order"`); declare `depth_axis="z"` and `shallow_end="min"` or `"max"` to measure it from the shallow contact whatever the row order (`depth_anchor="shallowest"`). A motif that puts the deep layers at the declared shallow end rejects the fit; the reason is `rejection_reason="declaration_contradicted"` only for a fit that passes every other acceptance test, and a weaker fit reports its own reason. A declaration with `orientation="deep_to_superficial"` raises `ValueError` before any fit.
- `jnwb.label_layers(vflip_result, probe_geometry, *, granular_thickness_um=400.0, depth_axis=None, shallow_end=None)`: Layer labels relative to a verified crossover contact. Every channel is `'na'` when `vflip_result.accepted` is False -- layers are never imputed onto a rejected fit. Pass the same `depth_axis` and `shallow_end` the fit used; a different declaration raises.
- `jnwb.curate_and_label(lfp, fs, *, pitch_um, erp=None, erp_times_ms=None)`: Bad-contact detection, short-run interpolation and graded layer labels for epoched LFP `(n_channels, n_epochs, n_samples)`, every width in micrometers. Returns `LaminarCurationResult`: read `grade` before `labels`. A and B carry a laminar claim, C (unstable or inconsistent) and D (vFLIP rejected, motif crossing alone) are sensitivity checks, and F sets every label to `"na"`. xFLIP and the evoked CSD are reported as distances to the anchor and never move it; the xFLIP distance is NaN when `xflip.accepted` is False. `band_low_hz`/`band_high_hz` shape the motif profiles, not the vFLIP anchor; bands must end below `fs / 2`. One cortical sheet is assumed: `n_crossings` above 1 means the shaft needs splitting. The probe, not the contact, is the unit of inference.
- The parts of `curate_and_label`: `jnwb.detect_bad_channels(data, fs)`, `jnwb.interpolate_channel_runs(data, bad_mask)`, `jnwb.evoked_csd_sink(erp, times_ms, *, pitch_um)` (the `erp` must be aligned to the stimulus itself) and `jnwb.fuse_laminar_anchors()`, which grades an anchor from per-window estimates.

### The workflow, step by step
Each step names the operations it composes. Operations other than the rows above are routed by the skill in brackets; a step with no jnwb operation is caller code, and the rule is stated so it can be written once.

| Step | Rule | Operations |
|---|---|---|
| 1. Events | Flash onsets; without a flash, the first stimulus of each correct trial. Each event time moves by the session's photodiode delay (step 7) and goes to the nearest LFP sample, a tie going to the later sample. | `events`, `epoch_continuous` (`jnwb-paradigm`) |
| 2. Relative power | Trial-mean PSD per channel, divided at each frequency by its maximum across the probe's channels. This is the published normalization; `vflip` normalizes by the range across contacts instead. | `compute_psd` with `axis=-1` (`jnwb-lfp-spectral`); the division is caller code |
| 3. Motif test | The published vFLIP2 code (Mendoza-Halliday et al., Dryad doi:10.5061/dryad.9w0vt4bnp) is the reference estimator. A probe passes when omega > 12, or 6 < omega <= 12 with \|G\| > 0.5, the code's two good-fit tiers. `vflip` is a second estimator with its own acceptance test (section 3, item 1). | `vflip`, `vflip_from_lfp` |
| 4. Noise strategies | Every combination of segment (whole probe, first half or second half, the halves split at the midpoint), channel subset (all, odd, even; the spacing doubles for odd or even) and median filter across channels (kernel 3, 5, 7 or 9, zero-padded ends), subset first and filter second. Per probe, for the grand average: both halves as two entries if each passes (two cortical folds); otherwise the whole probe if it passes; otherwise the one half that passes; otherwise the probe is noise. Within a segment the passing strategy with the largest omega (with `vflip`, the largest `support_score`) wins; ties go to all channels, then to the smaller kernel. | `vflip` with `contact_spacing`; `curate_and_label` for bad contacts and short-run interpolation as a separate route; the median filter is caller code |
| 5. Alignment | Depth is contact position minus the crossover, times the spacing, positive superficial. The side holding the alpha-beta peak is deep, so an inverted probe is flipped. Entries go onto one grid (for example -1000 to +1000 µm in 25 µm steps) by linear interpolation inside each entry's own channel range, never beyond it, with equal weight per entry. A depth is shown only where at least half the entries cover it, with the n per depth. | `vflip` (`crossover_depth_um`, `depth_axis`, `shallow_end`), `label_layers` |
| 6. Evoked CSD | Trial-mean ERP with each channel's mean over -50 to 0 ms removed; CSD at a neighbor separation of n contacts of the chosen subset, h = n times its spacing, conductivity 0.4 S/m; n of 3, 5, 7 or 9 where at least 2n + 3 channels remain. Each CSD row sits at its center channel and is aligned as in step 5. Negative is a sink. The depth of the most negative CSD 20-100 ms after onset is a check on the crossover, never a selection. | `current_source_density_1d` on every n-th channel, interleaved (`jnwb-lfp-spectral`); `evoked_csd_sink` |
| 7. Photodiode delay | Per session, the median over events of the lag from event code to luminance step. Sources in order: the analog photodiode trace (baseline the median of -50 to 0 ms; step the largest deviation in 0 to 250 ms; onset the first sample past half the step; an event counts only when its step exceeds three times the largest baseline deviation); then the detected-change table (first change in (0, 200] ms after the code); then a fixed constant, flagged. A source is used only when it answers for at least half the events. Both estimates and the interquartile range are kept for every session. | No jnwb operation; caller code over the event tables (`jnwb-paradigm`) |

## 3. Invariants & Safeguards
1. **`vflip` is not vFLIP2.** A `vflip` crossover is never a vFLIP2 crossover, and the omega and G tiers of step 3 never apply to `support_score`: `VFlipResult` carries no omega. Report the two as two estimators, and say which one placed every anchor.
2. **The parity artifact.** An odd neighbor separation pairs each channel with channels of the other parity, so any gain or offset difference between odd and even channels enters the CSD as a term that alternates in sign from row to row. A CSD that alternates on all channels while the odd-only and even-only CSDs are smooth shows that mismatch, not laminar structure; report the single-parity CSDs beside the all-channel one and per-probe odd/even ERP amplitude ratios.
3. **Choosing the best strategy is a selection.** Fix the strategy grid, the choice rule and the pass rule before any result, report every strategy's result for every probe, and never present the pass rate of chosen strategies as a property of the raw recordings.
4. **No filling.** A probe that passes under no strategy is noise and gets no anchor; a probe of unknown spacing is not analyzed; a depth outside an entry's own channels is not extrapolated; an area with no passing probe is reported empty.
5. **A crossover is a depth on this probe.** Calling it layer 4 is an inference; the earliest-sink check of step 6 tests that inference and drops no entry. `label_layers` labels every channel `'na'` on a rejected fit.
6. **The event, not the code.** The CSD and ERP are aligned to the luminance step, so the photodiode delay comes before the epoching, and a session on the fixed constant is flagged in every table that carries it.

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
n = 3
erp = rng.normal(size=(n_ch, 300))
csd = np.full_like(erp, np.nan)
for r in range(n):
    csd[r + n::n][: len(erp[r::n]) - 2] = jnwb.current_source_density_1d(
        erp[r::n], pitch_um=n * pitch_um, conductivity_s_per_m=0.4)
```

## 5. Verification
- On the full-probe frame, the odd and even crossovers of the example lie within one subset spacing (twice the pitch) of the whole probe's; subsets that disagree by more are reported, not averaged.
- The interleaved CSD equals $-\sigma\,(V_{j-n} - 2V_j + V_{j+n})/h^2$ with $h = n \times$ pitch in meters on rows `n` to `n_ch - n - 1`, and is NaN on the first and last `n` rows.
- For the parity check, scale the odd channels of a smooth ERP by a constant other than 1: the all-channel CSD at an odd n zigzags from row to row, and the single-parity CSDs only change scale.
- An aligned grand average keeps the n of entries per depth; no depth is drawn from fewer than half of them.

## 6. Documentation
- [`docs/laminar.md`](../../docs/laminar.md)
- [`docs/10_operation_specifications.md`](../../docs/10_operation_specifications.md)
- [`docs/references.md`](../../docs/references.md)
