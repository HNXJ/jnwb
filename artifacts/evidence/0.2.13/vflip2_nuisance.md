# vFLIP2 acceptance under nuisance conditions (0.2.13)

Written by `python scripts/vflip2_nuisance.py --write`. Every number is computed by that script from the probe records in `vflip2_nuisance.json`.

## Design

- Probes: 100 per cell. Probe i of every cell takes SeedSequence child 16 + i of entropy 0x1511 (the children of `scripts/vflip2_recovery.py`) and depth z0 = 8 + i mod 16, as the recovery run's null and planted probes do.
- Null sets: SNR 0. Planted sets: SNR 4, except the SNR sweep, which plants at each SNR in its table. Default cell: tau 0.03 s, no shared reference, 100 um, SNR 4, 1 kHz.
- Colored noise: the background AR(1) time constant tau_s. Shared reference: an AR(1) with tau 0.03 s, drawn from the probe's generator after the probe's own draws, added to every contact at variance ratio r to the background.
- Estimator: `jnwb.vflip2_from_lfp` at its defaults, with `contact_spacing` set by the cell. The frequency sweep keeps 5 s of data: n_samples = 5 fs.
- Acceptance: the accepted fraction of n (null acceptance in null sets, planted acceptance in planted sets).
- Planted recovery: accepted, and |z_hat - z0| <= 1 contact, over n. It is within one contact of the generator's z0, which mixes model mismatch with the nuisance effect; the oracle measure is in `vflip2_recovery.md` for the default cell only.
- Intervals: exact two-sided 95% Clopper-Pearson, `_ci` of `scripts/vflip2_recovery.py` (it calls `jnwb.clopper_pearson`).
- Refusals: a probe the estimator refuses is recorded with its message. It counts as not accepted, and n counts every probe of the cell.
- Default cell check: its null gives 24 of 100; vflip2_recovery.json gives 24 of 100 for the matched SNR-0 null. Probe mismatches: accepted 0, window 0, child and depth 0, omega 0, zhat 0 (omega and zhat to relative 1e-12).

## Colored noise (background time constant tau_s)

| Set | Setting | n | Acceptance, k of n, 95% CI | Planted recovery, k of n, 95% CI | Refused |
|---|---|---|---|---|---|
| null | tau 0.005 s | 100 | 21 of 100, 95% CI [0.1349, 0.3029] | none | 0 |
| planted | tau 0.005 s | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 27 of 100, 95% CI [0.1861, 0.368] | 0 |
| null | tau 0.03 s (default cell) | 100 | 24 of 100, 95% CI [0.1602, 0.3357] | none | 0 |
| planted | tau 0.03 s (default cell) | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |
| null | tau 0.1 s | 100 | 24 of 100, 95% CI [0.1602, 0.3357] | none | 0 |
| planted | tau 0.1 s | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 29 of 100, 95% CI [0.2036, 0.3893] | 0 |
| null | tau 0.3 s | 100 | 25 of 100, 95% CI [0.1688, 0.3466] | none | 0 |
| planted | tau 0.3 s | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 29 of 100, 95% CI [0.2036, 0.3893] | 0 |

Source: `vflip2_nuisance.json`, `sweeps.colored`: each cell's probe records; counts and intervals are `measures()` of those records.

Refusals: none.

## Shared reference (variance ratio to the background)

| Set | Setting | n | Acceptance, k of n, 95% CI | Planted recovery, k of n, 95% CI | Refused |
|---|---|---|---|---|---|
| null | ratio 0 (default cell) | 100 | 24 of 100, 95% CI [0.1602, 0.3357] | none | 0 |
| planted | ratio 0 (default cell) | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |
| null | ratio 0.5 | 100 | 20 of 100, 95% CI [0.1267, 0.2918] | none | 0 |
| planted | ratio 0.5 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 33 of 100, 95% CI [0.2392, 0.4312] | 0 |
| null | ratio 1 | 100 | 19 of 100, 95% CI [0.1184, 0.2807] | none | 0 |
| planted | ratio 1 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 29 of 100, 95% CI [0.2036, 0.3893] | 0 |
| null | ratio 2 | 100 | 11 of 100, 95% CI [0.0562, 0.1883] | none | 0 |
| planted | ratio 2 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 34 of 100, 95% CI [0.2482, 0.4415] | 0 |

Source: `vflip2_nuisance.json`, `sweeps.shared`: each cell's probe records; counts and intervals are `measures()` of those records.

Refusals: none.

## Spacing (contact_spacing)

| Set | Setting | n | Acceptance, k of n, 95% CI | Planted recovery, k of n, 95% CI | Refused |
|---|---|---|---|---|---|
| null | 25 um | 100 | 0 of 100, 95% CI [0.0, 0.0362] | none | 0 |
| planted | 25 um | 100 | 37 of 100, 95% CI [0.2756, 0.4724] | 14 of 100, 95% CI [0.0787, 0.2237] | 0 |
| null | 50 um | 100 | 0 of 100, 95% CI [0.0, 0.0362] | none | 0 |
| planted | 50 um | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 26 of 100, 95% CI [0.1774, 0.3573] | 0 |
| null | 100 um (default cell) | 100 | 24 of 100, 95% CI [0.1602, 0.3357] | none | 0 |
| planted | 100 um (default cell) | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |
| null | 150 um | 100 | 37 of 100, 95% CI [0.2756, 0.4724] | none | 0 |
| planted | 150 um | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |
| null | 200 um | 100 | 39 of 100, 95% CI [0.294, 0.4927] | none | 0 |
| planted | 200 um | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |

Source: `vflip2_nuisance.json`, `sweeps.spacing`: each cell's probe records; counts and intervals are `measures()` of those records.

Refusals: none.

## SNR (planted sets; the null is SNR 0)

| Set | Setting | n | Acceptance, k of n, 95% CI | Planted recovery, k of n, 95% CI | Refused |
|---|---|---|---|---|---|
| null | snr 0 (default cell) | 100 | 24 of 100, 95% CI [0.1602, 0.3357] | none | 0 |
| planted | snr 0.5 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 24 of 100, 95% CI [0.1602, 0.3357] | 0 |
| planted | snr 1 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 24 of 100, 95% CI [0.1602, 0.3357] | 0 |
| planted | snr 2 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 28 of 100, 95% CI [0.1948, 0.3787] | 0 |
| planted | snr 4 (default cell) | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |
| planted | snr 8 | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 30 of 100, 95% CI [0.2124, 0.3998] | 0 |

Source: `vflip2_nuisance.json`, `sweeps.snr`: each cell's probe records; counts and intervals are `measures()` of those records.

Refusals: none.

## Frequency grid (fs; n_samples = 5 s)

| Set | Setting | n | Acceptance, k of n, 95% CI | Planted recovery, k of n, 95% CI | Refused |
|---|---|---|---|---|---|
| null | 500 Hz | 100 | 22 of 100, 95% CI [0.1433, 0.3139] | none | 0 |
| planted | 500 Hz | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 31 of 100, 95% CI [0.2213, 0.4103] | 0 |
| null | 1000 Hz (default cell) | 100 | 24 of 100, 95% CI [0.1602, 0.3357] | none | 0 |
| planted | 1000 Hz (default cell) | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 32 of 100, 95% CI [0.2302, 0.4208] | 0 |
| null | 2000 Hz | 100 | 14 of 100, 95% CI [0.0787, 0.2237] | none | 0 |
| planted | 2000 Hz | 100 | 100 of 100, 95% CI [0.9638, 1.0] | 30 of 100, 95% CI [0.2124, 0.3998] | 0 |

Source: `vflip2_nuisance.json`, `sweeps.grid`: each cell's probe records; counts and intervals are `measures()` of those records.

Refusals: none.
