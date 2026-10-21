# 15-11 design: a generator that plants vFLIP2's own crossover

Ruled 2026-10-15 (`artifacts/rulings/2026-10-15.md`, row "15-11 design"). This file is the acceptance contract for 15-11. The item in `artifacts/todo_stack.md` points here. It was revised the same day after a review against the code: the oracle PSD is now estimated, not analytic; the grid run is now feasible; and draw order, tie-breaking and band matching are stated.

## What vFLIP2 estimates

`vflip2` (`jnwb/laminar/_vflip2.py`) searches windows of rows `[p, d]` (`:324-327`):
1. In each window, every frequency is divided by its maximum over the window's rows: $\tilde P(f, z; W) = P(f, z) / \max_{u \in W} P(f, u)$ (`:330`).
2. The two half-means of $\tilde P$ are smoothed by `_movmean5` (`:335-336`), and `_freqbands` picks the bands from them (`:107`, `:338`).
3. The band profiles average the unsmoothed $\tilde P$ over each band's frequencies (`:341-342`). Normalization comes first, then aggregation.
4. The crossover follows `_crossover`'s row rule (`:185`).

The estimand is therefore $z^*_W$, the crossover of the band-averaged normalized profiles for window $W$. In general it is not the depth $z_0$ where the planted band powers are equal. With no background and a window symmetric about $z_0$, $z^*_W = z_0$; an asymmetric window or the low-pass AR background moves it (derived).

## Generator

`jnwb.testing.synth_vflip2_crossover`, a new public function. It leaves every existing generator unchanged.

- **Geometry:** 32 contacts at `pitch_um=100`. The planted depth $z_0$ is a contact index from 8 to 23, which keeps it at least `minrange` rows from both ends. `fs=1000` Hz, `n_samples=5000`.
- **Draw order**, from one `Generator` (`resolve_rng`; no global RNG):
  1. the background, shape `(n_channels, n_samples)`: the stationary first sample, then the innovations;
  2. the low-band source;
  3. the high-band source.
  The null (`snr=0`) makes the same draws, so a planted probe and its null with the same seed hold identical backgrounds.
- **Background:** AR(1) with $\tau = 30$ ms and $\phi = e^{-1/(f_s \tau)}$ ($\approx 0.9672$ at 1 kHz). The innovation s.d. is $\sqrt{1 - \phi^2}$ and the first sample is drawn from the stationary distribution, so the variance is 1 from the first sample at any `fs` or $\tau$. It is independent across contacts.
- **Sources:**
  - Independent white noise, one draw per contact.
  - Band-passed by a 4th-order zero-phase Butterworth: low band 18 ± 5 Hz, high band 75 ± 15 Hz.
  - Each contact's filtered source is then rescaled to unit sample variance.
- **Profiles:**
  - One line through $(z_0, 0.5)$: $w_L(z) = 0.5 + (z - z_0)/(n_{\mathrm{ch}} - 1)$ for contact index $z$, and $w_H(z) = 1 - w_L(z)$. The low band rises with contact index, as `synth_laminar_motif`'s default orientation has it.
  - The slope is the same on both sides of $z_0$, so a window symmetric about $z_0$ keeps $z^*_W = z_0$ in the noiseless case.
  - $w_L$ is clipped to [0.05, 0.95], so no contact has zero power in either band.
  - A contact's signal is $\sqrt{\mathrm{snr}}\,(\sqrt{w_L}\,s_L + \sqrt{w_H}\,s_H)$.
- **SNR:** the ratio of the planted signal's total variance to the background's total variance at each contact. SNR 4 is the primary scenario. It is a total-variance ratio, not an in-band ratio, and it is not comparable with `synth_laminar_motif`'s amplitude multiplier.
- **Receipt:** $z_0$, the planted bands, `fs`, $\tau$, $\phi$, `snr` and the weights per contact.

## Oracle

The oracle PSD is estimated through the estimator's own front end, so leakage and the 1..150 Hz grid (`:426-448`, `:541`) match every measured run:
1. Generate a long record at the planted parameters: 200 one-second trials, from a `SeedSequence` child that no measured run uses.
2. Average `_psd_hanning` over those trials.
3. Freeze the resulting PSD, with its seed, in `artifacts/evidence/0.2.13/vflip2_oracle.json` before any measured run.

For every window `vflip2` visits, the oracle records, from that PSD and the pipeline above:
- $z^*_W$ with the planted bands;
- $z^*_W$ with the bands `_freqbands` picks;
- the picked bands;
- the eligibility flags (`:357-365`).

A window is **defined** when the planted weights inside it are not constant on either side of a crossover, that is, when not every row of the window is clipped at 0.05 or at 0.95. In a window that is not defined, the planted profiles are flat, and $z^*_W$ is recorded as undefined (`null`), never as a number. Such a window enters no localization measure: an accepted probe whose selected window is undefined counts as "accepted, no planted crossover", reported as its own count.

A plain-numpy recomputation must reproduce every recorded crossover. This gate checks transcription only. Validity rests on two checks:
- the noiseless control;
- agreement between two oracle PSDs built from independent long records. In every defined window, $z^*_W$ with the planted bands must agree within one contact.
  - The trial count is set by this agreement and by nothing measured. Build pairs at 200, 800 and 3200 one-second trials. Freeze the oracle at the smallest count where the planted-band check passes, and record the disagreement at every count.
  - A window where one oracle of the pair finds a planted-band crossover and the other does not is **indeterminate**: at oracle precision, whether a crossover exists there is unresolved. It is handled like an undefined window: $z^*_W$ is `null`, it enters no localization measure, and an accepted probe that selects it is counted as "accepted, indeterminate oracle". The agreement check covers the windows where both oracles find a crossover, and the indeterminate count is reported at every trial count. This rule was added after the 3200-trial diagnostic and before any measured run: 1 and 4 of 5616 windows were indeterminate, and every other difference was at most one contact.
  - If 3200 trials do not pass, stop and report.
  - $z^*_W$ with the picked bands, and the picked bands themselves, are reported with the between-oracle disagreement as oracle uncertainty. They are not gated.

## Runs

| Run | Probes | Seeds |
|---|---|---|
| Noiseless control (background off) | 16, one per $z_0$ in 8..23 | 16 recorded children |
| Primary planted, SNR 4 | 100 | `SeedSequence(entropy)`, 100 spawned children |
| Matched null, SNR 0 | 100 | the same children as the planted run |
| Geometry reversal (rows flipped) | 100 | the same children |
| Frequency grid: `vflip2` called directly on 0.5 Hz bins: `scipy.signal.periodogram(window="hann", nfft=2000)` on two-second trials at 1 kHz, averaged over trials, restricted to 1..150 Hz. `_psd_hanning` fixes integer-Hz bins (`_vflip2.py:395`) | 100 | new children |

The evidence file records the entropy value and every child index.

Geometry reversal is expected to mirror the selected window and flip the orientation label. That holds up to `vflip2`'s first-visited tie-breaking (`:366`, strict `>`), so the rate of exact omega ties is reported beside the mirror rate.

The grid run changes `binsize` and so `f_span` in omega (`:348`), on purpose: it measures what the grid does to acceptance and to localization.

## Measures, each a count with an exact two-sided 95% Clopper-Pearson interval (`jnwb.clopper_pearson`)

1. Detection: accepted / n.
2. Conditional localization, among accepted probes: $|\hat z - z^*_{\hat W}| \le 1$ contact.
   - The oracle for the selected window $\hat W$ is computed with the bands the noisy run picked.
   - The count is also reported with the oracle's own bands.
   - The band-mismatch rate is its own count.
3. Unconditional recovery: accepted and $|\hat z - z^*_{\hat W}| \le 1$, over n.
4. Error against the planted depth, $|\hat z - z_0|$, as a histogram, reported separately from 2 and 3.
5. Window selection: the selected $(p, d)$, and whether $z_0$ lies inside it.
6. Null acceptance: k / 100.

The targets are at least 90/100 for measure 3 and at most 5/100 for measure 6. Both are descriptive benchmarks. A count that meets a target is not a certified bound: with 5 of 100, the upper limit exceeds 5%. A missed target is reported as missed, in a machine-readable field (`"target_met": false`), and never relabelled.

## Tests

The CI tests (`tests/test_vflip2_recovery.py`) check structure and reproducibility only:
- the noiseless control at one seed runs and returns an accepted crossover inside its selected window. How close it lands to the background-off oracle is a measure in the evidence file, never a test assertion;
- two seeds give different probes;
- one seed gives the same probe twice;
- a planted probe and its null hold identical backgrounds;
- $\phi$, the stationary variance and the SNR match their definitions within sampling tolerance;
- the oracle file matches the plain-numpy recomputation.

The calibration outcome lives in the evidence file, not in a test assertion, so a missed target cannot turn the suite red.

## Separating the failure modes

| Mode | Evidence |
|---|---|
| Model mismatch | $z^*_W \ne z_0$ in the oracle |
| Estimator bias | the noiseless control misses $z^*_W$ |
| Noise sensitivity | measure 2 falls from the noiseless control to SNR 4 |
| False detection | measure 6 |

## Fixed, never tuned

`omega_cut = 6`, the generator's defaults and the seeds. Each is fixed before the first measured run.

Stop if:
- the oracle disagrees with the implemented transformation;
- the two oracle PSDs disagree;
- a benchmark setting changes after an unfavourable result;
- the estimator or window provenance is missing;
- synthetic results are presented as empirical evidence.

Andre Bastos's simulation code, the item's second half, runs the same table later.
