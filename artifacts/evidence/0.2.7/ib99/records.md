# IB-99: zflip per-pair surrogate test

Baseline 2611fa84. Ruling: `artifacts/rulings/2026-09-28.md`, row "`zflip` pair coupling test".
Pristine runs import a `git archive 2611fa84 jnwb` copy; each script asserts `jnwb.__file__`.

## Change

Each adjacent pair's wPLI is counted against the same surrogate's pair wPLI with
`_count_at_least_as_extreme(..., "greater")`, inside the loop that already tests the mean, so
no further draws are made and `p_value` is unchanged. Pair p = (1 + k) / (1 + n_surrogates); a
pair with p > `alpha` is not identifiable. The loop moved ahead of the depth fit. With
`n_surrogates=0` (or a flat contact, which skips the surrogates) the pair gate is not applied.

## False-accept rate, independent contact

`calibrate_independent_contact.py <tree> [per-seed]`. 5-contact 10-40 Hz wave, 2 samples per
contact, 8000 samples; one contact replaced by independent unit-SD noise, seeds 10000-10099;
`n_surrogates=50`, `alpha=0.05`. End contact: 0 on odd seeds, 4 on even.

| Contact | Noise | Baseline accepted | Repaired accepted | Repaired, accepted tau / true |
|---|---|---|---|---|
| end | bandpassed 10-40 Hz | 7/100 | 1/100 | 3.43 |
| end | white | 7/100 | 1/100 | 3.46 |
| end | 1/f^2 | 7/100 | 1/100 | 3.50 |
| interior (2) | bandpassed 10-40 Hz | 0/100 | 0/100 | - |
| interior (2) | white | 0/100 | 0/100 | - |
| interior (2) | 1/f^2 | 0/100 | 0/100 | - |

Identical counts with `rng=0` for every seed and with `rng=<noise seed>` (per-seed). The
surrogate test's level for one null pair is 2/51 = 0.039 (p takes values k/51; p <= 0.05 needs
k <= 2). 1/100 is within it (exact binomial 95% upper bound 0.054). The three noise types use
the same seeds and give nearly the same pair statistics (`list_accepted_seeds.py`), so they
are not three independent samples. The one repaired acceptance is seed 10078, contact 4, pair
wPLI 0.275, R^2 0.86, in both tree runs.

Baseline acceptances (`list_accepted_seeds.py`): seeds 10035, 10045, 10048, 10049, 10069,
10078, 10094 for every noise type, tau/true 3.23 to 5.31, omnibus p 0.0196 each.

## Clean wave

Seed 11, 8000 samples, default band: tau 0.001990567277416379 on both trees, bit-identical, and
bit-identical on both trees across n in {2000, 4000, 6000, 8000, 16000}, bands (15, 35) and
(10, 40), `n_surrogates` 0 and 50. The value 0.0020155597348266753 quoted for this construction
was not reproduced at 2611fa84 in any of those 20 variants; tau does not depend on the
surrogates, and the repair changes only which pairs are identifiable.

## Short records

`short_record_power.py <tree>`, the construction of `tests/test_zflip_audit.py` (6 contacts,
noise 0.005), 20 surrogate seeds per cell, accepted count on the repaired tree:

| N (segments) | 19 surrogates | 99 | 199 |
|---|---|---|---|
| 256 (3) | 0/20 | 0/20 | 0/20 |
| 512 (7) | 14/20 | 20/20 | 20/20 |
| 1024 | 20/20 | 20/20 | 20/20 |
| 2048 | 20/20 | 20/20 | 20/20 |

Every refusal is the pair test. At 3 segments the clean pair wPLI is exactly 1.0 and more than
a fraction `alpha` of independent-phase surrogates tie it, so no surrogate count lets a pair
pass. `test_a_clean_wave_is_detected_at_every_supported_length[256]` asserted acceptance at
N=256 and failed in the full suite; it now asserts the delay is identified with the test off
and acceptance for N > 256, and `test_three_segments_cannot_show_a_pair_coupled` pins the
refusal at 256.

## Ramp width

`measure_ramp_width.py <tree>`, ratio = rms residual of the least-squares line in eps of max|x|,
width 1000.

| Row | Ratio |
|---|---|
| exact ramps, 2000 draws, n 1e3-1e5, slope/offset 1e-6-1e6 | 0.148 to 1.45 |
| cumsum ramps n=1000 / 4000 / 8000 / 16000 / 32000 (max of 300) | 28.7 / 102 / 252 / 475 / 832 |
| cumsum ramps n=1e5 (max of 300) | 3430; 85 of 300 above 1000 |
| `3.0 + np.cumsum(np.full(8000, 0.1))` | 72.55, refused |
| unit-SD signal on offset 1e10 / 1e11 / 1e12 | 4.5e5 / 4.5e4 / 4.5e3, kept |

Cumsum ramps grow roughly linearly with n; from about 32000 samples some exceed 1000 and are
measured rather than refused. At n=1e5 the cumsum maximum (3430) is within 1.3x of a unit-SD
signal on a 1e12 offset (4503), so no single width separates both at that length.

## Discrimination

`discriminate.py <tree> 2611fa84` swaps `jnwb/laminar.py`, runs each new test alone, restores,
and compares SHA-256 (restore matched).

| Variant | cumsum ramp refused | 1e11 offset kept | independent contact refused |
|---|---|---|---|
| repaired | pass | pass | pass |
| baseline 2611fa84 | pass | pass | **fail** |
| width 1 | **fail** | pass | pass |
| width 1e6 | pass | **fail** | pass |
| pair gate removed | pass | pass | **fail** |

The two ramp tests guard behaviour the baseline already has; each fails on the width mutant it
is named against.
