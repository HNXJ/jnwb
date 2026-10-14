# Statistical Inference

Group comparisons, non-parametric resampling, bootstrap confidence intervals, label
permutation with explicit exchangeability, false discovery rate (FDR) control, and cluster-based
permutation testing.

Run the executable tutorial:

```bash
python examples/tutorials/05_statistics.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## The figure

![Two synthetic groups of trial rates with their difference, and a cluster permutation test over time bins](../assets/figures/fig24_statistics_groups_cluster.png#only-light)
![Two synthetic groups of trial rates with their difference, and a cluster permutation test over time bins](../assets/figures/fig24_statistics_groups_cluster.dark.png#only-dark)

Synthetic: two groups of trial rates and a time series with an injected effect, from the seeded inputs the tutorial draws. Panel A gives the difference of group means, A minus B, and the 95% bootstrap interval the library returns for it. Panel B is the mean of each condition over time bins, with the cluster that `jnwb.cluster_permutation_test` finds shaded; its p-value and permutation count are in the legend. The effect was injected, so the cluster shows the test working on this input and says nothing about real data.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/05_statistics.py"
```
