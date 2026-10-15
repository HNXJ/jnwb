# 15-11 design: a generator that plants vFLIP2's own crossover

Ruled 2026-10-15 (`artifacts/rulings/2026-10-15.md`, row "15-11 design"). This file is the acceptance contract for 15-11. The item in `artifacts/todo_stack.md` points here.

## What vFLIP2 estimates

`vflip2` (`jnwb/laminar/_vflip2.py`) searches windows of rows `[p, d]`:
1. In each window, every frequency is divided by its maximum over the window's rows: $\tilde P(f, z; W) = P(f, z) / \max_{u \in W} P(f, u)$ (`:330`).
2. Bands are chosen from the window's two half-means (`_freqbands`, `:107`).
3. The band profiles average $\tilde P$ over the band's frequencies (`:341-342`): normalization comes first, then aggregation.
4. The crossover is `_crossover`'s row rule (`:185`).

The estimand is therefore $z^*_W$, the crossover of the band-averaged normalized profiles for window $W$. In general it is not the depth $z_0$ where the planted band powers are equal.

## Generator

`jnwb.testing.synth_vflip2_crossover`, a new public function. It leaves every existing generator unchanged.

- **Geometry:** 32 contacts at `pitch_um=100`. The planted depth $z_0$ is a contact index drawn from contacts 8 to 23, which keeps it at least `minrange` rows from both ends. `fs=1000` Hz, `n_samples=5000`.
- **Background:** AR(1) with $\tau = 30$ ms, $\phi = e^{-1/(f_s \tau)}$ ($\approx 0.9672$ at 1 kHz). The innovation s.d. is $\sqrt{1 - \phi^2}$, so the background's stationary variance is 1 at any `fs` or $\tau$. It is independent across contacts.
- **Bands:** low band 18 ± 5 Hz and high band 75 ± 15 Hz, from band-passed white noise (4th-order Butterworth, zero phase). Each source is scaled to unit variance.
- **Profiles:** linear weights $w_L(z)$ and $w_H(z) = 1 - w_L(z)$ in band power, equal (0.5) at $z_0$, and reaching 0 and 1 at the probe ends. A contact's signal is $\sqrt{\mathrm{snr}}\,(\sqrt{w_L}\,s_L + \sqrt{w_H}\,s_H)$.
- **SNR:** the variance ratio of the planted signal to the background at every contact; SNR 4 is the primary scenario. This differs from `synth_laminar_motif`'s amplitude multiplier, so its SNR 4 is not comparable.
- **Randomness:** `rng` is a `Generator` or an int, through `resolve_rng`; there is no global RNG. A planted probe and its null share the background stream.
- **Receipt:** returns $z_0$, the planted bands, `fs`, $\tau$, $\phi$, `snr` and the expected PSD $E[P(f, z)]$ on `vflip2_from_lfp`'s frequency grid (signal plus background, analytic).

## Oracle

The oracle is built before any noisy run, from the expected PSD alone, and frozen to `artifacts/evidence/0.2.13/vflip2_oracle.json`. For every window `vflip2` would visit, it records:
- $z^*_W$ from the planted bands, through the estimator's normalize-then-average order and `_crossover`'s rule;
- $z^*_W$ from the bands `_freqbands` picks on the expected PSD;
- whether the window is eligible under the estimator's peak and range checks.

The oracle calls the estimator's private helpers on the expected PSD, never on a noisy realization. Gate: the oracle's crossover differs from an independent recomputation (plain numpy, no jnwb helper) in any window -> stop.

## Runs

| Run | Probes | Seeds |
|---|---|---|
| Noiseless control (background off, SNR undefined) | 1 per $z_0$ in 8..23 | none |
| Primary planted, SNR 4 | 100 | `SeedSequence(entropy)`, 100 spawned children |
| Matched null, SNR 0 | 100 | the same children as the planted run |
| Geometry reversal (rows flipped) | 100 | the same children |
| Frequency grid (half-width bins via `n_samples=10000`) | 100 | new children |

The evidence file records the entropy value.

## Measures, each a count with an exact two-sided 95% Clopper-Pearson interval (`jnwb.clopper_pearson`)

1. Detection: accepted / n.
2. Conditional localization: $|\hat z - z^*_{\hat W}| \le 1$ contact, among accepted probes, against the oracle of the selected window.
3. Unconditional recovery: accepted and $|\hat z - z^*_{\hat W}| \le 1$, over n.
4. Error against the planted depth: $|\hat z - z_0|$, reported as a histogram, separately from 2 and 3.
5. Window selection: the selected $(p, d)$, and whether $z_0$ lies inside it.
6. Null acceptance: k / 100.

The targets, at least 90/100 for measure 3 and at most 5/100 for measure 6, are descriptive benchmarks. A count that meets a target is not a certified bound: with 5 of 100, the upper limit exceeds 5%. A missed target is reported as missed, in a machine-readable field (`"target_met": false`), and never relabelled.

## Tests

The CI tests (`tests/test_vflip2_simulation.py`) check only structure and reproducibility:
- the noiseless control recovers $z^*_W$ within one contact;
- two seeds give different probes;
- one seed gives the same probe twice;
- a planted probe and its null share the background;
- $\phi$ and the stationary variance match their definitions;
- the oracle matches the independent recomputation.

The calibration outcome lives in the evidence file, not in a test assertion, so a missed target cannot turn the suite red.

## Separating the failure modes

| Mode | Evidence |
|---|---|
| Model mismatch | $z^*_W \ne z_0$ in the oracle |
| Estimator bias | the noiseless control misses $z^*_W$ |
| Noise sensitivity | measure 2 falls from the noiseless control to SNR 4 |
| False detection | measure 6 |

## Fixed, never tuned

`omega_cut = 6`, the generator's defaults, and the seeds. Each is fixed before the first noisy run.

Stop if:
- the oracle disagrees with the implemented transformation;
- a benchmark setting changes after an unfavourable result;
- the estimator or window provenance is missing;
- synthetic results are presented as empirical evidence.

Andre Bastos's simulation code, the item's second half, runs the same table later.
