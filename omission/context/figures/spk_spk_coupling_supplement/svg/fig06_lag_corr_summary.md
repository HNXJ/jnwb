# Figure 6 headline -- SPK-SPK lead/lag correlation, corrected-family summary

Full family (12,033 cells: scope x node-pair x lag x condition-group, all cells with >=3 sessions) is corrected in `aggregate_population_spk_spk_lag_corr.py` and recorded in full at `outputs/population_spk_spk_lag_corr/lag_hit_rates.csv` -- THIS file lists only the survivors and is not itself a separate correction pass.

**4/12033 survive Holm-Bonferroni (FWER). 35/12033 survive BH-FDR.**

## Holm-Bonferroni survivors

| condition_group | scope | node1 | node2 | lag_ms | n_sessions | hit_rate | holm_p | bh_q |
|---|---|---|---|---|---|---|---|---|
| baseline | within_area | V4/Other | V4/S- | 0 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| baseline | within_area | V4/S+ | V4/S- | -10 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| stim | within_area | FEF/Other | FEF/S- | 0 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| stim | within_area | V4/S+ | V4/S- | 10 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |

## BH-FDR survivors (superset of the above)

| condition_group | scope | node1 | node2 | lag_ms | n_sessions | hit_rate | holm_p | bh_q |
|---|---|---|---|---|---|---|---|---|
| baseline | within_area | V4/Other | V4/S- | 0 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| baseline | within_area | V4/S+ | V4/S- | -10 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| stim | within_area | FEF/Other | FEF/S- | 0 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| stim | within_area | V4/S+ | V4/S- | 10 | 6 | 0.833 | 2.16e-02 | 5.41e-03 |
| stim | between_area | V1/S+ | V2/S+ | 20 | 4 | 1.000 | 7.52e-02 | 6.84e-03 |
| stim | within_area | PFC/Other | PFC/S+ | 0 | 7 | 0.714 | 7.25e-02 | 6.84e-03 |
| omission | between_area | V1/S+ | V2/S+ | -10 | 4 | 1.000 | 7.52e-02 | 6.84e-03 |
| baseline | within_area | TEO/Other | TEO/S- | 0 | 7 | 0.714 | 7.25e-02 | 6.84e-03 |
| stim | within_area | V1/Other | V1/S- | 0 | 4 | 1.000 | 7.52e-02 | 6.84e-03 |
| stim | within_area | V4/Other | V4/S+ | -10 | 7 | 0.714 | 7.25e-02 | 6.84e-03 |
| stim | within_area | TEO/Other | TEO/S- | 0 | 7 | 0.714 | 7.25e-02 | 6.84e-03 |
| stim | within_area | TEO/S+ | TEO/S- | 0 | 5 | 0.800 | 3.61e-01 | 2.41e-02 |
| baseline | within_area | TEO/S+ | TEO/S- | 0 | 5 | 0.800 | 3.61e-01 | 2.41e-02 |
| baseline | within_area | TEO/S+ | TEO/S- | -10 | 5 | 0.800 | 3.61e-01 | 2.41e-02 |
| omission | within_area | TEO/Other | TEO/S+ | 0 | 5 | 0.800 | 3.61e-01 | 2.41e-02 |
| baseline | within_area | V4/S+ | V4/S- | 0 | 6 | 0.667 | 1.00e+00 | 4.30e-02 |
| stim | within_area | MT/S+ | MT/S- | 0 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| stim | between_area | V3a/d/S+ | V4/S+ | 0 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| omission | between_area | PFC/Other | V4/O+ | -30 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| baseline | between_area | V1/S+ | V2/S- | 20 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | V2/S+ | V2/S- | 0 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| stim | within_area | V4/Other | V4/S- | 0 | 6 | 0.667 | 1.00e+00 | 4.30e-02 |
| stim | within_area | V4/S+ | V4/S- | 0 | 6 | 0.667 | 1.00e+00 | 4.30e-02 |
| stim | within_area | V4/S+ | V4/S- | 20 | 6 | 0.667 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | FEF/Other | FEF/S- | 0 | 6 | 0.667 | 1.00e+00 | 4.30e-02 |
| stim | within_area | V2/S+ | V2/S- | 30 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | V2/S+ | V2/S- | -30 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| omission | within_area | V4/S+ | V4/S- | 0 | 6 | 0.667 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | V2/S+ | V2/S- | -20 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| omission | between_area | V3a/d/S+ | V4/S+ | -60 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| stim | between_area | FEF/Other | TEO/S+ | 90 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | V2/S+ | V2/S- | -40 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| omission | between_area | V1/S+ | V2/S- | 10 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | V2/S+ | V2/S- | 10 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |
| baseline | within_area | V2/S+ | V2/S- | -10 | 3 | 1.000 | 1.00e+00 | 4.30e-02 |