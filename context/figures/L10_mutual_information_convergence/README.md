# L10 — mutual information convergence check

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json), same gate
as L1-L9. Per spec, this is explicitly **not an independent result** — it is a model-free
complement to [L7](../L7_cross_area_power_correlation/README.md)'s Pearson correlation, read
alongside it.

**Method**: imports `sessions_with_nodes`, `node_trial_traces`, and `correlation_matrix` directly
from L7's own module — the MI matrices are computed on the **exact same** per-trial,
per-trial-baselined, log-last band-power vectors L7 correlates, not a re-derived version of them,
so the two statistics are genuinely comparable on identical inputs.
`sklearn.feature_selection.mutual_info_regression` (k-NN continuous MI estimator) computes MI in
both directions per pair (not exactly symmetric under this estimator, both reported); the matrix
entry is their mean. Agreement statistic: Spearman ρ between the flattened upper-triangle MI
values and |Pearson r| values, per session/band/condition.

## Result (descriptive — no independent claim, per spec)

**Agreement between MI and |Pearson r| is consistently strongly positive**: Spearman ρ ranges
0.32–0.95 across all 3 sessions × 5 bands × 2 conditions (30 combinations), **every single one
positive**, median ρ ≈ 0.8. `sub-V182o_ses-260629` (the sparsest-coupling session per
[L7](../L7_cross_area_power_correlation/README.md)'s own finding) shows the weakest agreement
(0.32–0.79); `sub-V182o_ses-260702` and `sub-V182o_ses-260715` (denser coupling per L7) show
strong, tight agreement (0.66–0.95).

This is the convergence result the spec asks for: **MI and Pearson correlation are ranking node
pairs similarly across this corpus's band-power structure** — no evidence here of nonlinear
dependence that Pearson r would be missing (which would show up as low agreement despite real
MI). Per spec's own framing ("report as a convergence check, not an independent result"), this
is read as corroborating L7's correlation-based ranking, not as a separate finding about which
pairs are "truly" coupled.

## Self-test

`python L10_mutual_information_convergence.py --test`: (a) a linear synthetic pair (r=0.78)
shows substantial MI (0.50 nats) — sanity check. (b) A **nonlinear** pair (Y = (X−mean)² + noise,
Pearson r=−0.11 by construction) shows MI (1.10 nats) clearly above the independent baseline
(0.004 nats) — demonstrating exactly the complementary detection the spec's "model-free
complement" language describes: MI catches a real dependence Pearson r misses. (c) The agreement
statistic recovers a strong positive Spearman ρ=0.61 (p=0.017) on a set of pairs with smoothly
varying linear-dependence strength. (d) Determinism check.

Outputs: `L10.svg` / `L10.png` / `L10.pdf`, `L10_stats.json`, `L10_manifest.json`.
