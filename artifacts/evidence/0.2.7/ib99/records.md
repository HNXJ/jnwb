# IB-99: zflip per-pair surrogate test

Baseline 2611fa84. Ruling: `artifacts/rulings/2026-09-28.md`, row "`zflip` pair coupling test".
Pristine runs import a `git archive 2611fa84 jnwb` copy; each script asserts `jnwb.__file__`.

## Change

Each adjacent pair's wPLI is counted against the same surrogate's pair wPLI with
`_count_at_least_as_extreme(..., "greater")`, inside the loop that already tests the mean, so
no further draws are made and `p_value` is unchanged. Pair p = (1 + k) / (1 + n_surrogates); a
pair with p > `alpha` is not identifiable. The loop moved ahead of the depth fit.

Second commit, per Hamm's ruling that no pair is identifiable without its null: a pair whose
surrogates were not drawn has a NaN p and fails, so with `n_surrogates=0`, or a constant or
linear-in-time contact (which skips the surrogates), every pair is unidentifiable, tau is NaN
and `rejection_reason` says surrogates are needed to establish a delay. The first commit
(963d6550) left the gate unapplied there and still reported a delay.

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

| N | 19 surrogates | 99 | 199 |
|---|---|---|---|
| 256 | 0/20 | 0/20 | 0/20 |
| 512 | 14/20 | 20/20 | 20/20 |
| 1024 | 20/20 | 20/20 | 20/20 |
| 2048 | 20/20 | 20/20 | 20/20 |

Every refusal is the pair test. The cause is the in-band bin count, not the segment count
(the first commit's docstring wrongly gave 512 samples 7 segments). `tie_mass.py <tree>`, 1000
surrogates, fraction of surrogates whose pair wPLI ties or exceeds 1.0 by zflip's counting
rule:

| N | Segments | Bins in 15-35 Hz | Broadband wave | 25 Hz sinusoid |
|---|---|---|---|---|
| 256 | 3 | 3 | 0.099-0.111 | 0.146-0.181 |
| 512 | 3 | 5 | 0.004-0.008 | 0.036-0.046 |

A pair wPLI is the mean over in-band bins, so a surrogate reaches 1.0 only when every bin keeps
one sign of its imaginary cross-spectrum across the 3 segments; with 3 bins that is about 10%
of surrogates, above `alpha`, so no surrogate count lets a pair pass at 256 samples. At 512 a
narrowband wave sits near `alpha` (about 0.04).

Tests: `test_a_clean_wave_is_detected_at_every_supported_length` asserted acceptance at N=256
and failed in the full suite. It now covers 512, 2048 and 40000 with 199 surrogates (19 passed
at 512 in only 14 of 20 seeds), and
`test_three_in_band_bins_at_256_samples_cannot_show_a_pair_coupled` pins the refusal at 256
and that it is the pair test's rather than the frequency-support check's.

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

`discriminate.py <tree> 2611fa84 963d6550` swaps `jnwb/laminar.py`, runs each test alone,
restores, and compares SHA-256 (restore matched). Columns: A cumsum ramp refused, B 1e11
offset kept, C independent contact refused, D no delay at `n_surrogates=0`
(`test_no_surrogate_test_means_no_acceptance`), E pair `min_wpli` inclusive at threshold.

| Variant | A | B | C | D | E |
|---|---|---|---|---|---|
| repaired | pass | pass | pass | pass | pass |
| baseline 2611fa84 | pass | pass | **fail** | **fail** | pass |
| first repair 963d6550 | pass | pass | pass | **fail** | pass |
| width 1 | **fail** | pass | pass | pass | pass |
| width 1e6 | pass | **fail** | pass | pass | pass |
| pair gate removed | pass | pass | **fail** | **fail** | pass |
| pair `>= min_wpli` as `>` | pass | pass | pass | pass | **fail** |
| pair `>= min_wpli` as `<=` | pass | **fail** | **fail** | **fail** | **fail** |

A and B guard behaviour the baseline already has; each fails on the width mutant it is named
against. E was rebuilt on a significant weakest pair, because its old construction (identical
contacts, pair wPLI 0.0) now fails the surrogate test before the threshold is reached.

## Tests changed for the n_surrogates=0 ruling

Tests that read a delay or identifiability at `n_surrogates=0` now draw 50 surrogates with
`rng=0`, or assert the NaN where the test is about the untested case. The zero-gradient branch
("Delay gradient across contacts is zero to round-off") is no longer reached by
`test_zflip_identical_contacts_give_no_direction`: identical contacts have pair wPLI 0.0, which
every surrogate ties, so the pair test refuses first. No construction found reaches that
branch with every pair significant.
