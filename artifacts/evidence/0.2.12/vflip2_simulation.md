# vFLIP2 on seeded synthetic probes (0.2.12)

Written by `python scripts/vflip2_simulation.py --write`. Every number is computed by that script.

## Design

- Planted probe: `synth_laminar_motif(32, 5000, 1000.0, c_crossover=<generator crossover>, pitch_um=100.0, snr=4.0, rng=<seed>)`.
- Null probe: the generator at `snr=0.0`, which leaves its shared 1/f background noise only; a planted and a null probe with one seed share that background.
- Estimator: `jnwb.vflip2_from_lfp(lfp, 1000.0, contact_spacing=100.0)`, defaults.
- Seeds: 0 to 99 (100 probes per set).
- Generator crossover: 8 to 23, 6 to 7 probes per contact, contact = 8 + seed % 16.
- Within one contact: accepted, and `crossover_channel` within 1 contact of the generator's crossover.
- The generator's crossover is the contact where its gamma and beta amplitude weights are equal, and vFLIP2's is where the relative band-power profiles cross inside its selected window, so the offset below measures the gap between these two definitions, not an error rate.
- In raw power the 1/f background can mask the beta gradient at snr 4: for seed 5 the raw beta mean is 0.1694 on rows 0 to 13 and 0.1668 on rows 14 to 31.

## Counts

| set | probes | accepted | within one contact | accepted, more than one contact away | no window passed |
|---|---|---|---|---|---|
| planted | 100 | 93 | 20 | 73 | 7 |
| null | 100 | 18 | - | - | 73 |

## Omega and crossover offset

| set | probes with a window | omega min | omega median | omega max |
|---|---|---|---|---|
| planted | 93 | 6.511 | 8.601 | 9.967 |
| null | 27 | 4.832 | 6.236 | 7.219 |

Crossover minus generator crossover, accepted planted probes: min -12.000, median -2.000, max 18.000 (contacts).

## Per probe

| seed | generator crossover | planted accepted | planted crossover | planted omega | null accepted | null omega |
|---|---|---|---|---|---|---|
| 0 | 8 | True | 14 | 8.601 | False | - |
| 1 | 9 | True | 15 | 8.587 | False | - |
| 2 | 10 | True | 16 | 7.706 | False | - |
| 3 | 11 | True | 11 | 7.465 | False | - |
| 4 | 12 | False | - | - | False | - |
| 5 | 13 | True | 10 | 8.947 | True | 7.147 |
| 6 | 14 | True | 13 | 8.600 | True | 6.731 |
| 7 | 15 | True | 13 | 8.159 | False | - |
| 8 | 16 | True | 13 | 8.854 | False | - |
| 9 | 17 | True | 8 | 8.603 | True | 6.133 |
| 10 | 18 | True | 14 | 8.620 | False | 4.918 |
| 11 | 19 | True | 25 | 7.630 | False | - |
| 12 | 20 | True | 18 | 6.843 | False | - |
| 13 | 21 | True | 22 | 7.566 | True | 6.090 |
| 14 | 22 | True | 21 | 8.652 | True | 6.527 |
| 15 | 23 | False | - | - | False | - |
| 16 | 8 | True | 6 | 7.816 | False | - |
| 17 | 9 | True | 7 | 9.567 | False | - |
| 18 | 10 | True | 4 | 8.016 | False | - |
| 19 | 11 | True | 6 | 7.859 | False | - |
| 20 | 12 | True | 10 | 8.844 | True | 6.236 |
| 21 | 13 | True | 10 | 7.871 | False | - |
| 22 | 14 | True | 11 | 9.082 | True | 6.526 |
| 23 | 15 | True | 26 | 7.661 | False | - |
| 24 | 16 | True | 15 | 8.841 | False | - |
| 25 | 17 | True | 10 | 8.037 | False | - |
| 26 | 18 | True | 10 | 8.601 | False | - |
| 27 | 19 | True | 25 | 8.117 | False | - |
| 28 | 20 | True | 18 | 8.466 | False | - |
| 29 | 21 | True | 18 | 8.688 | False | - |
| 30 | 22 | True | 24 | 7.810 | False | - |
| 31 | 23 | False | - | - | False | - |
| 32 | 8 | True | 26 | 8.005 | False | - |
| 33 | 9 | True | 3 | 8.283 | False | - |
| 34 | 10 | True | 6 | 9.703 | False | - |
| 35 | 11 | True | 10 | 9.057 | False | - |
| 36 | 12 | True | 9 | 9.089 | False | - |
| 37 | 13 | True | 16 | 9.470 | True | 6.573 |
| 38 | 14 | True | 15 | 8.982 | False | - |
| 39 | 15 | True | 17 | 8.887 | False | - |
| 40 | 16 | True | 23 | 8.797 | True | 6.129 |
| 41 | 17 | True | 19 | 9.967 | False | - |
| 42 | 18 | True | 15 | 8.622 | True | 6.542 |
| 43 | 19 | True | 21 | 7.305 | False | - |
| 44 | 20 | True | 22 | 8.842 | True | 7.219 |
| 45 | 21 | True | 19 | 8.401 | False | - |
| 46 | 22 | True | 15 | 7.661 | False | - |
| 47 | 23 | True | 12 | 9.084 | False | - |
| 48 | 8 | True | 10 | 9.606 | False | - |
| 49 | 9 | True | 21 | 6.837 | True | 6.735 |
| 50 | 10 | True | 10 | 8.657 | False | - |
| 51 | 11 | True | 9 | 9.191 | False | 4.945 |
| 52 | 12 | True | 11 | 9.590 | True | 6.749 |
| 53 | 13 | True | 12 | 8.478 | False | - |
| 54 | 14 | True | 8 | 9.426 | False | - |
| 55 | 15 | True | 19 | 8.859 | False | - |
| 56 | 16 | True | 14 | 7.613 | False | - |
| 57 | 17 | True | 12 | 8.860 | False | - |
| 58 | 18 | True | 15 | 9.452 | True | 6.208 |
| 59 | 19 | True | 16 | 9.025 | False | 5.379 |
| 60 | 20 | True | 22 | 8.277 | False | 5.555 |
| 61 | 21 | True | 15 | 8.622 | False | 5.793 |
| 62 | 22 | True | 18 | 8.392 | False | - |
| 63 | 23 | True | 19 | 8.235 | False | - |
| 64 | 8 | True | 8 | 8.761 | False | - |
| 65 | 9 | True | 7 | 8.007 | True | 6.345 |
| 66 | 10 | True | 12 | 8.843 | False | - |
| 67 | 11 | True | 13 | 8.281 | False | - |
| 68 | 12 | True | 11 | 8.910 | False | - |
| 69 | 13 | True | 9 | 8.876 | False | - |
| 70 | 14 | True | 11 | 8.967 | False | - |
| 71 | 15 | True | 10 | 8.702 | False | - |
| 72 | 16 | True | 6 | 9.621 | False | - |
| 73 | 17 | True | 8 | 9.428 | False | - |
| 74 | 18 | True | 19 | 8.222 | False | 5.501 |
| 75 | 19 | True | 22 | 8.294 | True | 6.971 |
| 76 | 20 | False | - | - | False | - |
| 77 | 21 | True | 20 | 8.325 | False | - |
| 78 | 22 | True | 20 | 8.541 | False | - |
| 79 | 23 | True | 14 | 8.260 | False | - |
| 80 | 8 | True | 18 | 7.538 | False | - |
| 81 | 9 | True | 5 | 8.387 | False | - |
| 82 | 10 | False | - | - | False | - |
| 83 | 11 | True | 5 | 8.137 | False | - |
| 84 | 12 | True | 7 | 9.211 | False | - |
| 85 | 13 | True | 12 | 9.217 | True | 7.044 |
| 86 | 14 | True | 13 | 8.458 | False | - |
| 87 | 15 | True | 14 | 7.854 | False | - |
| 88 | 16 | True | 17 | 8.170 | False | - |
| 89 | 17 | True | 9 | 7.712 | True | 6.270 |
| 90 | 18 | True | 14 | 8.075 | False | - |
| 91 | 19 | True | 10 | 6.511 | False | - |
| 92 | 20 | True | 16 | 8.940 | False | 5.413 |
| 93 | 21 | False | - | - | False | - |
| 94 | 22 | True | 21 | 8.773 | False | - |
| 95 | 23 | True | 11 | 9.341 | False | 5.960 |
| 96 | 8 | True | 9 | 7.658 | False | 4.832 |
| 97 | 9 | False | - | - | False | - |
| 98 | 10 | True | 7 | 8.784 | False | - |
| 99 | 11 | True | 8 | 8.794 | False | - |
