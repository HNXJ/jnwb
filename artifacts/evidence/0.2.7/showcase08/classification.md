# Docs-08 showcase: independent reproduction and classification

Critic pass at `db4b3aab`, 2026-09-28, with its own probes (its TE reimplementation matches `jnwb.transfer_entropy` to 1e-15). Every rate is P(p < 0.05) and every ± is 2 SE. "zl" is X = s + 0.5 e1, Y = s + 0.5 e2 with s white.

| Finding | Reproduced | Mechanism | Class | Item |
|---|---|---|---|---|
| TE `bias_correction='mm'` under zl | yes. At n = 2000, bins 4: 0.112 ±0.028 and 0.084 ±0.025. At n = 500: 0.127. At n = 8000: 0.072. At bins 8: 0.373. Without the correction: 0.048 and 0.046. Independent controls: 0.037-0.053 | the null removes the zero-lag X-Y dependence, so the observed table has fewer occupied cells (ΔK -3.6 at bins 4, -120 at bins 8) and a larger Miller-Madow term. Without the correction the test is conservative at large state spaces (bins 8, k = l = 2: 0 of 300) | required-0.2.7 | IB-96 |
| TE on a coloured common source | rejects in 1.000 of cases, as does the Granger F-test | real predictability: X's past carries s beyond Y's noisy past. "Use quantile" holds only for a white source | required-0.2.7 (docs) | IB-96 |
| PSI surrogate p under zl | yes. nperseg 100: 0.174 ±0.034. nperseg 50: 0.463. nperseg 200: 0.017. Trial permutation 10×400: 0.327. Jackknife 1×2000: 0.0655 ±0.011 | PSI telescopes under coherent zero-lag input, while the shift null's variance scales with bins and segments; the result can be liberal or conservative by setting | required-0.2.7 | IB-97 |
| PSI power at the default nperseg | yes, low power with a valid p. Power: surrogate 0.020, jackknife 0.005. At nperseg 100: jackknife 0.375. A warning fires | noise SD 0.090 against 0.58 | deferred-0.2.8, plus the docs example | IB-98 and the deferred bullet |
| `docs/08` topology and conditioning | yes. Density 1.0 in 20 of 20 seeds. With 50 surrogates a lone edge's q is at least 0.118. Common driver: 1.000 bivariate, 0.035 given Z | Granger is non-negative, so a threshold of 0 keeps every edge; `directed_network` is pairwise | required-0.2.7 (docs) | IB-98 |

Deferral attack on P-227: its premise, that the test is conservative and so cannot make evidence falsely pass, holds only under independence. Under zl the jackknife is liberal at 0.0655, and IB-97 makes it the lead p, so IB-97 states the rate.
