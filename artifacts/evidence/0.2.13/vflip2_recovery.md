# vFLIP2 recovery on planted probes (0.2.13, item 15-11)

Written by `python scripts/vflip2_recovery.py --write`. Every number is computed by that script.

- Probes per run: 100. Noiseless control: 16 (one per depth).
- Frozen oracle trial counts: one-second 800, two-second grid 200.
- Oracle disagreement between independent pairs A and B. Gated: defined windows where both find a planted crossover. Indeterminate: exactly one finds one (null, no localization measure). Picked bands, picked crossovers and edge shifts (Hz, windows where both have bands): uncertainty only.

| oracle | trials | indeterminate | planted beyond 1 contact | planted max | picked beyond 1 contact | picked max | picked bands differ | edge shift median (Hz) | edge shift max (Hz) | planted gate |
|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 200 | 24 | 1 | 2.0 | 186 | 3.0 | 5571 | 3.0 | 28.0 | no |
| s1 | 800 | 10 | 0 | 1.0 | 916 | 4.0 | 5580 | 4.0 | 53.0 | yes |
| s1 | 3200 | 1 | 0 | 1.0 | 371 | 3.0 | 5585 | 3.0 | 34.0 | yes |
| s2 | 200 | 20 | 0 | 1.0 | 110 | 3.0 | 5594 | 2.0 | 69.0 | yes |
| s2 | 800 | 6 | 0 | 1.0 | 70 | 5.0 | 5602 | 2.0 | 49.5 | yes |
| s2 | 3200 | 4 | 0 | 1.0 | 133 | 2.0 | 5593 | 1.5 | 34.0 | yes |
| control, background off | 800 | 11 | 0 | 1.0 | 10 | 1.0 | 552 | 0.0 | 62.0 | yes |

- Pool check (5 probes, serial vs ProcessPoolExecutor): identical.
- Estimator agrees with the reimplemented window table on every probe: yes.
- Children: SeedSequence(0x1511) spawned 260 children; noiseless control 0-15, primary/null/reversal 16-115, grid 116-215; oracle pairs s1 200 A 216, s1 200 B 217, s1 800 A 218, s1 800 B 219, s1 3200 A 220, s1 3200 B 221, s2 200 A 222, s2 200 B 223, s2 800 A 224, s2 800 B 225, s2 3200 A 226, s2 3200 B 227; background-off control pairs 228-259

## Measures

| # | Measure | Count | Target |
|---|---|---|---|
| 1 | Detection (accepted / n) | 100 of 100, 95% CI [0.9638, 1.0] | none |
| 2 | Conditional localization, picked bands, defined selected window (among those) | 29 of 100, 95% CI [0.2036, 0.3893] | none |
| 2b | Same, oracle's own bands | 53 of 100, 95% CI [0.4276, 0.6306] | none |
| 2c | Band-edge shift vs oracle's own bands, selected window (median 16.0 Hz, max 26.0 Hz; every edge within 1 Hz: 0 of 100, 95% CI [0.0, 0.0362]) | none |
| 2d | Accepted, no planted crossover (selected window undefined) | 0 | none |
| 2e | Accepted, indeterminate oracle (selected window indeterminate) | 0 | none |
| 3 | Unconditional recovery (accepted, scored, within 1 contact, / n) | 29 of 100, 95% CI [0.2036, 0.3893]; target 90 of 100: missed | at least 90 of 100 |
| 4 | Error against planted depth, accepted (contacts: count) | 0: 9, 1: 23, 2: 27, 3: 14, 4: 15, 5: 6, 6: 5, 7: 1 | none |
| 5 | Window selection: window contains z0 | 100 of 100; 8 distinct windows | none |
| 6 | Null acceptance (k / n) | 24 of 100, 95% CI [0.1602, 0.3357]; target 5 of 100: missed | at most 5 of 100 |

## Other runs

- Noiseless control against the background-off oracle (800 trials per record, A/B pair): 16 accepted of 16; undefined 0; indeterminate 0; no crossover in either oracle 0; scored 16; within one contact 13 of 16, 95% CI [0.5435, 0.9595]; misses beyond one contact (estimate minus oracle z*, contacts): z0 8 +2, z0 9 +2, z0 10 +3; by size: 2 contacts: 2, 3 contacts: 1.
- Background-off pair gate: passes (planted beyond 1 contact where both find one: 0; indeterminate: 11; plain mismatches: 0).
- model mismatch, background on vs off: 11 of 16, 95% CI [0.4134, 0.8898] of the scored probes within one contact of the background-on oracle's picked-band crossover.
- Geometry reversal: detection 100 of 100, 95% CI [0.9638, 1.0]; mirror 100 of 100; orientation flipped 100 of 100; exact omega ties 0 of 100 (primary), 0 of 100 (reversed).
- Frequency grid (0.5 Hz, 299 bins, oracle 200 two-second trials): detection 100 of 100, 95% CI [0.9638, 1.0]; recovery 63 of 100, 95% CI [0.5276, 0.7244]; within one contact (picked) 63 of 100, 95% CI [0.5276, 0.7244].

