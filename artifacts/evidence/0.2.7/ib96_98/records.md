# IB-96, IB-97, IB-98: calibration and page records

Run 2026-09-28 on the tree of `57fb3deb` (its parent `af487ea5` for the "before" columns), jnwb
imported from the lane worktree; every script asserts `jnwb.__file__` lies inside the tree it is
given. Every rate is P(p < 0.05) at a nominal 0.05, and a band is 0.05 plus or minus 2 SE at the
seed count shown. "zl" is X = s + 0.5 e1, Y = s + 0.5 e2 with s white: coupled at zero lag, with
no directed coupling and no lead.

| Script | What it measures |
|---|---|
| `calibrate.py <tree> te\|psi\|all <seeds>` | the TE and PSI grids below, 22 worker processes |
| `te_large_n.py <tree> <seeds> <offset> <n>...` | TE under zl at the given lengths on a fresh seed offset |
| `pin_counts.py <tree>` | the rejection counts the two pinned tests assert, on any tree |
| `run_page08.py <tree> [<seeds>]` | every python block of `docs/08` in order, then the network, PSI and Z examples over data seeds |
| `run_page.py <tree> <page>` | every python block of one docs page in order |

## Transfer entropy

Default `bias_correction='mm'`, 199 surrogates, quantile bins 4, k = l = 1 unless stated.

| Setting | Seeds | X->Y | Y->X | 2 SE band | Before (critic, `db4b3aab`) |
|---|---|---|---|---|---|
| zl n=500 | 3000 | 0.031 | 0.028 | 0.042-0.058 | 0.127 / 0.127 |
| zl n=2000 | 3000 | 0.051 | 0.047 | 0.042-0.058 | 0.112 / 0.084 |
| zl n=4000 | 5000 | 0.053 | 0.058 | 0.044-0.056 | not measured |
| zl n=8000 | 2000 | 0.054 | 0.061 | 0.040-0.060 | 0.073 / 0.097 |
| zl bins 8, n=2000 | 1000 | 0.000 | 0.000 | 0.036-0.064 | 0.373 / 0.340 |
| zl k=l=2, n=2000 | 1000 | 0.000 | 0.000 | 0.036-0.064 | 0.003 / 0.000 |
| independent n=2000 | 1000 | 0.036 | 0.048 | 0.036-0.064 | 0.043 / 0.053 |
| independent n=500 | 1000 | 0.039 | 0.043 | 0.036-0.064 | not measured |
| independent AR(1) n=2000 | 1000 | 0.062 | 0.048 | 0.036-0.064 | 0.037 / 0.040 |

Pooled rows, by batch (seed offset; X->Y / Y->X):

| Setting | `calibrate.py`, 1000 seeds | `te_large_n.py` 50000, 2000 seeds | `te_large_n.py` 90000, 2000 seeds |
|---|---|---|---|
| zl n=500 | 0.032 / 0.032 | not run | 0.030 / 0.026 |
| zl n=2000 | 0.048 / 0.044 | 0.052 / 0.049 | not run |
| zl n=4000 | 0.053 / 0.073 | 0.046 / 0.052 | 0.059 / 0.056 |
| zl n=8000 | not run | 0.054 / 0.061 | not run |

Two rows sit outside the band: n=500 below it (conservative), and n=4000 Y->X and n=8000 Y->X
at or just above its upper edge. Both are under classification and are not stated as settled.

## Phase slope index

Lead p is `p_net` (the jackknife t test), band 5-100 Hz, fs 1000, 1000 seeds, band 0.036-0.064.

| Setting | Segments | zl | independent |
|---|---|---|---|
| 1 x 2000, nperseg 50 | 79 | 0.059 | 0.001 |
| 1 x 2000, nperseg 100 | 39 | 0.063 | 0.003 |
| 1 x 2000, nperseg 200 | 19 | 0.058 | 0.002 |
| 10 x 400, nperseg 100 | 70 | 0.070 | 0.000 |

With 199 surrogates at zl, nperseg 100 (500 seeds): lead p 0.068, identical, seed by seed, to the
run without surrogates; the coupling p, `diagnostics['p_coupling_surrogate']`, 0.174 (band
0.031-0.069). That coupling p is what `p_net` reported before.

## Pinned tests

`pin_counts.py` on each tree:

| Tree | TE bins 8, n 2000, 16 seeds x 2 directions | PSI nperseg 50, 20 seeds |
|---|---|---|
| `af487ea5` | 15 of 32 below 0.05, min p 0.020 | 9 of 20 |
| `57fb3deb` | 0 of 32, min p 0.080 | 0 of 20 |

The tests assert at most 2. With the `af487ea5` `jnwb/connectivity.py` copied into the tree, the
two new test classes gave 5 failed, 1 passed (the power test survives, as it should); the restore
was checked by SHA-256.

## docs/08

`run_page08.py <tree> 20`: all 8 blocks ran. Over 20 data seeds the network's q-mask topology gave
density 1/6 in 18 and 0.5 in 2 (true graph: one edge of six), where `threshold=0.0` on the raw
matrix gave 1.0 in 20 of 20; the PSI example's lead p fell below 0.05 in 0.85; the common-driver
example was significant in 1.00 pairwise and 0.00 given Z.
