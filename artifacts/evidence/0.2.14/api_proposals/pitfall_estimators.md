<!-- Drafted 2026-10-20 by a read-only reviewer against 7ea17995; ruled as recorded in artifacts/rulings/2026-10-20.md. Kept as drafted. -->

RESULT: Read-only proposal drafted; nothing implemented.
CHANGES: none.
COMMANDS: none (read-only; no suite run).
EVIDENCE: file reads below; line citations mark observed claims, "inferred" marks reasoning.
OPEN: none (proposal awaits owner rulings).

# Proposal: four connectivity-pitfall estimators for jnwb

Written against `7ea17995`. Nothing here is implemented. Each shape is ruled before code (scope ruled 2026-09-29, per packet).

## Conventions every estimator inherits (observed)

- Input contract: `X`/`Y` in the forms `as_trials` accepts — 1-D `(n_times,)`, 2-D `(n_trials, n_times)`, or list of 1-D trials — normalized to `(n_trials, n_times)` float; 3-D+, empty, or non-finite input raises `ValueError` (`jnwb/connectivity/_trials.py:16-86`).
- Pairing: `X`/`Y` resolved by `_pair_trials`, shapes must match exactly (`jnwb/connectivity/_trials.py:89-97`).
- Result type: `DirectedResult` with `method, x_to_y, y_to_x, net, unit, p_*, per_band, spectrum, n_trials, n_times, fs, params, diagnostics` (`jnwb/connectivity/_common.py:46-82`); `None` p means not computed (`jnwb/connectivity/_common.py:60`).
- Surrogate null: `_surrogate_source` destroys cross-signal timing while keeping each trial's autocorrelation — trial permutation at ≥ 7 trials, circular shift of each trial below that (`jnwb/connectivity/_common.py:167-188`); threshold `_MIN_TRIALS_FOR_TRIAL_PERMUTATION = 7` (`jnwb/connectivity/_common.py:157`); scheme recorded in `params['surrogate_scheme']` via `_surrogate_scheme` (`jnwb/connectivity/_common.py:160-164`). Randomness via `_surrogate_rng = recorded_rng` (`jnwb/connectivity/_common.py:147`); seed-entropy round-trip (`params['surrogate_seed_entropy']` back as `rng` reproduces p) is the documented pattern in `granger` (`jnwb/connectivity/_granger.py:573-576`), `granger_spectral` (`jnwb/connectivity/_granger.py:885-886`), `phase_slope_index` (skill routing row, `skills/jnwb-connectivity/SKILL.md:17`), `transfer_entropy` (`jnwb/connectivity/_transfer_entropy.py:257-261`).
- Non-finite draw rule already in force (observed, `jnwb/connectivity/_common.py:208-210`): a non-finite observed gives NaN; `B` counts draws that are not NaN, with `+inf`/`-inf` included; NaN draws leave `n`.
- Order check: `_fixed_order` refuses `0`, fractions, bools; integral floats accepted (`jnwb/connectivity/_common.py:13-29`).
- Naming precedent (observed): exports are verbs/nouns — `granger`, `granger_spectral`, `phase_slope_index`, `transfer_entropy`, `directed_connectivity`, `directed_network` (`jnwb/__init__.py:490-495`), `cross_area_coherence`, `imaginary_coherency`, `wpli` (`jnwb/__init__.py:461-469`); deprecated alias `granger_causality` emits `DeprecationWarning` (`jnwb/connectivity/_granger.py:357-360`).
- Epistemic language (observed): Granger/PSI/TE give predictive directionality under an observational model, never causal verbs (`skills/jnwb-connectivity/SKILL.md:29`); coupling vs direction vs delay per safeguard 4 (`skills/jnwb-connectivity/SKILL.md:32`); volume-conduction safeguard binds every operation here (`skills/jnwb-connectivity/SKILL.md:33`); nonparametric multitaper route of Bastos et al. 2020 / Vezoli et al. 2021 is not implemented and values must not be matched to it (`skills/jnwb-connectivity/SKILL.md:35`); `granger`/`granger_spectral` fit a parametric VAR (`skills/jnwb-connectivity/SKILL.md:36`), `granger_spectral` docstring states Wilson factorization "is not needed here and is not implemented" (`jnwb/connectivity/_granger.py:859-864`).
- Facts binding the design (observed, `artifacts/fact_stack.md:77-86`): S5 every randomness consumer takes `rng`, nothing calls `np.random.seed()`; S10 permutation null names its exchangeability scheme; S11 result reports the `rng` used; S6 device/workers change no number; S8 estimand text uses no higher claim-class vocabulary (`claim classes`: `magnitude, lag asymmetry, delay, inference`, `artifacts/fact_stack.md:121`); S13 latency/velocity only under verified linear unwrapped phase-frequency relation with predeclared identifiability criteria; S14 no `immunity` vocabulary (`immunity, immune, complete suppression`, `artifacts/fact_stack.md:122`).
- Rule 4.7 (observed, `AGENTS.md:67`): call the library function, never retype its rule.
- Format precedent: `artifacts/evidence/0.2.8/api_proposals/nwb_mutation.md` — bounds table from fact rows, per-operation signature + refusals table, what-is-left-out, then graded questions.

## E1 `granger_nonparametric` — nonparametric spectral Granger by spectral factorization

```python
def granger_nonparametric(
    X, Y,
    *,
    fs: float,
    n_freqs: int = 256,
    bands,
    n_surrogates: int = 0,
    rng: RNGLike = Default(0),
    detrend: Optional[str] = "zscore",
    time_axis: int = -1,
    seed: Any = Default(0),
) -> DirectedResult:
```

- Name (inferred): noun phrase matching `granger_spectral`; `nonparametric` adjective distinguishes the Wilson-factorization route from the parametric Geweke route without a new verb.
- No default supplies scientific meaning (inferred): `fs` and `bands` are required (no `None` meaning "canonical"); `n_freqs`, `n_surrogates`, `rng`, `detrend`, `time_axis` are execution/display controls with the same defaults as `granger_spectral` (`jnwb/connectivity/_granger.py:839-854`). There is deliberately no `order` parameter — the estimator fits no VAR (this is the point of the comparison).
- Estimand (one sentence): frequency-resolved nonparametric Granger influence X→Y and Y→X from the Wilson-factorized cross-spectral matrix, in log variance ratio (dimensionless log ratio), per frequency and per band.
- Inputs and axes: any `as_trials` form, paired by `_pair_trials` to identical `(n_trials, n_times)` (`jnwb/connectivity/_trials.py:89-97`).
- Refuses with `ValueError`: non-positive/non-finite `fs` (as `granger_spectral` does, `jnwb/connectivity/_granger.py:908-909`); `X`/`Y` shape mismatch; 3-D+, empty, or non-finite input (via `as_trials`); fewer than 2 Welch segments (same identifiability guard as `cross_area_coherence`, `jnwb/spectral/_coupling.py:98-120`); `bands` naming no bin (same convention as `granger_spectral` per-band NaN + warning, `jnwb/connectivity/_granger.py:994-1002`, inferred to reuse); constant (all-equal) input → NaN estimate (same convention as `cross_area_coherence`, `jnwb/spectral/_coupling.py:465-480`, inferred to reuse).
- Null/inference: reuses `_surrogate_rng`, `_surrogate_source`/`_surrogate_scheme`, `_surrogate_p` with `scale=1.0` log-ratio convention (`jnwb/connectivity/_granger.py:1039-1041`); reports `surrogate_seed_entropy` + `surrogate_scheme` in `params`; non-finite draw rule as in force (`jnwb/connectivity/_common.py:208-210`). No analytic null (as `granger_spectral` states there is none, `jnwb/connectivity/_granger.py:883`).
- Result object: `DirectedResult`, `unit='log variance ratio'`, `method='granger_nonparametric'`, `spectrum={freqs, gc_x_to_y, gc_y_to_x}`, `per_band[name]={value, value_reverse, peak_hz, peak_hz_reverse, band_hz, n_freq_bins, p_surrogate}`, `p_x_to_y`/`p_y_to_x` surrogate (else `None`), `p_net=None` (same shape as `granger_spectral`, `jnwb/connectivity/_granger.py:1050-1090`).
- Reuse (rule 4.7): trial handling via `as_trials`/`_pair_trials`/`_detrend_trials` (`jnwb/connectivity/_trials.py:16-115`); cross-spectral matrix via the Welch path `cross_area_coherence`/`_welch_csd_gpu` already use (`jnwb/spectral/_coupling.py:377-386`, `_compute_all` estimator-plumbing `jnwb/spectral/_coupling.py:388-444`); only the factorization (Wilson) and Geweke-from-factorized-matrix step are new; band averaging reuses the trapezoidal `_mean_over` integral (`jnwb/connectivity/_granger.py:970-978`).
- Synthetic test proving it: planted case — bivariate VAR of known order with unidirectional coupling X→Y (same generator style as the skill receipt, `skills/jnwb-connectivity/SKILL.md:38-51`); synthetic identity: `granger_nonparametric` band/full-spectrum value agrees with `granger(X, Y, order=<true order>).x_to_y` / `granger_spectral(X, Y, fs, order=<true order>)` total within a predeclared tolerance (the packet's required identity). Null case: independent white-noise pair → estimate near 0 with surrogate p uniform (reject ≈ nominal); zero-lag-mixed common source → reported as coupling with no direction claimed (safeguard 4).
- References: Dhamala, Rangarajan & Ding 2008 — to add; Wilson spectral factorization — to add. Pitfall context: Bastos & Schoffelen 2016, already in `docs/references.md` (`doi:10.3389/fnsys.2015.00175`, observed `docs/references.md:161`).

## E2 `granger_time_reversed` — time-reversed Granger control for SNR asymmetry

```python
def granger_time_reversed(
    X, Y,
    *,
    order,
    n_surrogates: int = 0,
    rng: RNGLike = Default(0),
    detrend: Optional[str] = "zscore",
    time_axis: int = -1,
    seed: Any = Default(0),
) -> DirectedResult:
```

- Name (inferred): `granger_`-prefixed control matching `granger_spectral`; "time_reversed" names the operation, not a claim.
- No default supplies scientific meaning (inferred): `order` (int ≥ 1 via `_fixed_order`, or `"auto"` reusing `granger`'s selection) is required — no silent order. Whether `"auto"` is offered or order is strictly required is Q3 below.
- Estimand: net directed asymmetry and its time-reversal signature: forward net flow minus reverse-time net flow, in log variance ratio.
- Inputs and axes: as E1. Time reversal = flip each trial along the time axis, then run the identical estimator; never a pooled or concatenated flip (inferred requirement from the no-pooling rule, `AGENTS.md:71`).
- Refuses with `ValueError`: same input refusals as `granger` (shape mismatch via `_pair_trials`; `require_trial_length` history check as `granger` does, `jnwb/connectivity/_granger.py:614-623`); bad `order` via `_fixed_order` (`jnwb/connectivity/_common.py:13-29`); degenerate (non-positive/non-finite) residual variance → NaN, not 0 (the `granger` convention, `jnwb/connectivity/_granger.py:660-666`).
- Decision rule (proposed, to be ruled): a directed claim requires the net flow to flip sign under time reversal — `sign(net_reversed) == -sign(net_forward)` with both magnitudes above their surrogate nulls; otherwise the result reports `diagnostics['warnings'] += ['no_sign_flip_on_time_reversal']` and `ok == False`, declining the directed inference. Reference for the rule: Haufe et al. 2013 — to add; Vinck et al. 2015 — to add (both absent from `docs/references.md`, observed by search during this run — inferred as "absent", file read `docs/references.md:53-164`).
- Null/inference: reuses `granger`'s surrogate machinery (`_surrogate_rng`, `_surrogate_source`, `_surrogate_p`, non-finite rule as above); the reversal itself is a fixed transformation, not a random draw, so `rng`/`surrogate_seed_entropy` semantics are unchanged (inferred).
- Result object: `DirectedResult`, `unit='log variance ratio'`, `method='granger_time_reversed'`, `x_to_y`/`y_to_x` = forward flows, `diagnostics` carrying `net_forward`, `net_reversed`, `sign_flip` bool; `per_band={}` (time-domain, as `granger`).
- Reuse (rule 4.7): computes both directions by calling `granger` (or its `_one_direction` path, `jnwb/connectivity/_granger.py:642-683`) on forward and reversed trials — never a retyped VAR; order selection reuses `_granger_order_criteria`/`_select_order` (`jnwb/connectivity/_granger.py:502-689`).
- Synthetic test proving it: planted case — unidirectional VAR X→Y with matched signal strength → forward `x_to_y > y_to_x`, reversed net flips sign, `sign_flip is True`. Pitfall case (the point): same coupling with asymmetric SNR (one channel noisier, per Bastos & Schoffelen 2016 pitfall row, `docs/references.md:161`) → forward asymmetry without sign flip → directed claim declined. Null case: independent pairs → nets near 0 both ways, p uniform.
- References: Haufe et al. 2013 — to add; Vinck et al. 2015 — to add; pitfall statement already held: Bastos & Schoffelen 2016 `doi:10.3389/fnsys.2015.00175` (`docs/references.md:161`).

## E3 `partial_coherence` — partial coherence conditioned on a third signal

```python
def partial_coherence(
    X, Y, Z,
    *,
    fs: float,
    freq_bands,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
    n_surrogates: int = 50,
    rng: RNGLike = DEFAULT_SEED,
    n_jobs: int = 1,
) -> dict:
```

- Name (inferred): noun matching `cross_area_coherence` / `imaginary_coherency`.
- No default supplies scientific meaning (inferred): `fs`, `freq_bands` (dict or `'canonical'`), and the conditioning signal `Z` are required — compare `cross_area_coherence` refusing `freq_bands=None` (`jnwb/spectral/_coupling.py:272-284`). `nperseg`/`noverlap` keep the `cross_area_coherence` defaults (`jnwb/spectral/_coupling.py:346-358`) as execution controls (inferred as non-scientific defaults, since they set resolution/averaging, not the hypothesis).
- Estimand: magnitude-squared coherence between X and Y after removing the linear contribution of Z, dimensionless in [0, 1], per band.
- Inputs and axes: three 1-D paired traces of equal length (same refusals as `_require_1d_pair`/`_require_equal_lengths`/`_require_finite_nonempty_pair`, `jnwb/spectral/_coupling.py:35-64`); refused: 2-D input, unequal lengths, empty, NaN/Inf (each `ValueError`, as `cross_area_coherence` does). Multichannel `Z` (conditioning on several nodes) is Q5 below; proposed initial shape conditions on one recorded signal only.
- Null/inference: reuses the circular-shift null of `cross_area_coherence` (`jnwb/spectral/_coupling.py:166-170`, `_compute_all` `jnwb/spectral/_coupling.py:388-444`) with `(count+1)/(n+1)` p-values and the reported `p_value_floor` (`jnwb/spectral/_coupling.py:311-313`); `rng` semantics and `surrogate_seed_entropy` round-trip as in `cross_area_coherence` (`jnwb/spectral/_coupling.py:191-204, 453`); shared-surrogate-across-bands dependence warning carried over (`jnwb/spectral/_coupling.py:434-442`); alternatively the trial-permutation scheme where trials exist — Q6 below.
- Result object: same dict shape as `cross_area_coherence` (`coherence_spectrum, frequencies, band_coherence, band_significance, peak_*, nperseg, noverlap, n_segments_used, device_used, n_surrogates_used, p_value_floor, surrogate_seed_entropy`) plus `conditioned_on` receipt; reuses no `DirectedResult` because the estimand is unsigned coupling (magnitude class, S8) — direction needs a signed estimator per safeguard 4 (inferred from `skills/jnwb-connectivity/SKILL.md:32`).
- Reuse (rule 4.7): segmentation/identifiability via `_require_identifiable_segmentation` + `MIN_IDENTIFIABLE_SEGMENTS = 2` (`jnwb/spectral/_coupling.py:98-130`); spectra via `_welch_csd_gpu`/SciPy path with the one-estimator rule (`jnwb/spectral/_coupling.py:377-401`); constant-input → NaN convention (`jnwb/spectral/_coupling.py:465-480`).
- Synthetic test proving it: planted case — X→Z→Y indirect chain (Z drives both X and Y with lags, no direct X–Y link): ordinary coherence X–Y is high, partial coherence given Z collapses toward the null. Null case: independent pairs → partial coherence at the ~1/K null expectation (`n_segments_used` reported, `jnwb/spectral/_coupling.py:240-244`). Common-input pitfall case per Bastos & Schoffelen 2016 (unrecorded-driver row is out of scope; recorded-driver row is this estimator's case).
- References: Geweke 1984 conditional measure (already held for `granger`/`directed_network`, `docs/references.md:69` and `jnwb/connectivity/_network.py:166-168`) as the time-domain analogue; partial-coherence spectral reference — to add.

## E4 `coherence_bias_floor` — randomly-paired-epoch bias floor for coherence and Granger

```python
def coherence_bias_floor(
    signals,
    *,
    fs: float,
    freq_bands,
    pairing: str = "random_pairs",
    n_draws: int = 200,
    rng: RNGLike = Default(0),
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
) -> dict:
```

- Name (inferred): noun naming the quantity (a floor), not an estimator verb; alternative `epoch_pairing_bias` is Q7.
- No default supplies scientific meaning (inferred): `fs`, `freq_bands` required; `pairing` names the scheme with a fixed default that is the scheme itself (inferred as legitimate: the default does not choose a hypothesis, it names the method), or required — Q7. `n_draws`/`rng` are execution controls.
- Estimand: the finite-sample bias level of coherence (dimensionless) and of Granger causality (log variance ratio) under random epoch pairing, per band: the value an uncoupled pair reaches by bias alone.
- Inputs and axes: epoched signals `(n_epochs, n_times)` (trials-as-epochs); pairing scheme: randomly pair epoch `i` of site A with epoch `j ≠ i` of site B (`rng`-drawn derangement, reusing `_surrogate_source` trial-permutation path at ≥ 7 epochs, `jnwb/connectivity/_common.py:167-188`), take the maximum over site pairs as the floor (per Vezoli et al. 2021 STAR Methods, `docs/references.md:162`). `Z` conditioning is out of scope here (inferred).
- Refuses with `ValueError`: fewer than 2 epochs usable for pairing; non-finite samples; `freq_bands=None`; band with no bins (omitted, as `cross_area_coherence` does, `jnwb/spectral/_coupling.py:429-433`).
- Null/inference: this estimator *is* a null constructor — it reuses `_surrogate_rng`/`recorded_rng` and reports the seed entropy (S11); exchangeability scheme named in `params` (S10): `"random_epoch_pairing_max_over_site_pairs"`. What the floor is compared with: the observed coherence / `granger_spectral` band value is significant only above the floor (the Vezoli rule, `docs/references.md:162`); the comparison statistic (max vs percentile) is Q8.
- Result object: dict `{floor_per_band, n_draws, pairing, max_over_pairs, seed_entropy, fs, freq_bands, n_segments_used}` (inferred shape; new receipt type, not `DirectedResult`, since it calibrates other estimators).
- Reuse (rule 4.7): epoch pairing via `_surrogate_source`; coherence via `cross_area_coherence`'s estimator path; Granger side via `granger_spectral`'s `_spectral_gc_from_var` surrogate path (`jnwb/connectivity/_granger.py:1093-1111`); p-floor reporting via `p_value_floor` convention (`jnwb/spectral/_coupling.py:311-313`).
- Synthetic test proving it: planted case — known-coupled narrowband pair: observed band coherence sits above the floor built from its own randomly paired epochs; null case — independent pairs: observed value at/below the floor, and the floor itself near the ~1/K null expectation. Cross-check (inferred): floor built by this function and `cross_area_coherence`'s circular-shift null disagree in the documented way (shift preserves within-epoch timing; random pairing breaks epoch alignment) — the difference is reported, not hidden.
- References: Vezoli et al. 2021, STAR Methods "Quantification and statistical analysis" — already in `docs/references.md` (`doi:10.1016/j.neuron.2021.09.052`, observed `docs/references.md:162`); that row already states jnwb "builds its null by circular shifts instead, and the paper's Granger causality is nonparametric, which jnwb does not implement" — this estimator closes the second half of that sentence (inferred consequence).

## What is left out, and why

| Left out | Reason |
|---|---|
| Matching Bastos/Vezoli published values with the current parametric path | already declined in the skill (`skills/jnwb-connectivity/SKILL.md:35`); E1 is the route to comparability |
| Causal verbs for any of the four | safeguard 1 (`skills/jnwb-connectivity/SKILL.md:29`); S8 claim classes |
| A default frequency band, order, or conditioning set | B3 / packet constraint: scientific choices are caller inputs |
| `immunity` language for E3 | S14; reduced sensitivity to zero-lag coupling only |
| Delay/velocity claims for any estimator | S13: only under verified linear unwrapped phase-frequency relation + predeclared identifiability criteria |
| Device/parity claims beyond S6 | `device`/`n_jobs` change no number (`artifacts/fact_stack.md:78`) |

## Questions for the owner (one decision each)

| # | Question | Options (recommendation first) |
|---|---|---|
| Q1 | E1 scope: full nonparametric estimator, or comparison receipt only? | (a) full `granger_nonparametric` as above, 80; (b) comparison receipt only (identity check helper, no new public estimator), 55; (c) defer E1, 30 |
| Q2 | E1 name | (a) `granger_nonparametric`, 75; (b) `nonparametric_granger`, 55; (c) `granger_wilson`, 50 |
| Q3 | E2 `order`: offer `"auto"` (reuse `granger` selection) or require a fixed int? | (a) fixed int only via `_fixed_order`, 70; (b) `"auto"` allowed, 55 |
| Q4 | E2 decision rule strictness | (a) sign-flip required for a directed claim (decline otherwise), 80; (b) flip reported as a warning only, claim stands, 45; (c) flip + magnitude-above-null on both sides, 60 |
| Q5 | E3 conditioning set: one signal or many? | (a) one `Z` only, 75; (b) list of conditioning signals (Geweke-1984 style, as `granger(Z=...)`), 55 |
| Q6 | E3/E4 trial null: which scheme? | (a) reuse `_surrogate_scheme` (permutation ≥ 7, shift below), 80; (b) always random epoch pairing regardless of trial count, 50 |
| Q7 | E4 shape: standalone function or method flag? | (a) standalone `coherence_bias_floor`, 70; (b) `bias_floor=True` flag on `cross_area_coherence`/`granger_spectral`, 45 |
| Q8 | E4 comparison statistic | (a) maximum over site pairs (Vezoli STAR Methods), 80; (b) 95th percentile over draws, 55; (c) full null distribution returned, p computed, 60 |