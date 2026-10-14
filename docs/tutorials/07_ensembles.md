# Ensembles and Population Dynamics

Representational dissimilarity matrices (RDM), second-order RDM similarity, Joint RSA (JRSA)
across time, and nested cross-validated linear SVM population decoding.

Run the executable tutorial:

```bash
python examples/tutorials/07_ensembles.py
```

`examples/` ships in neither the wheel nor the sdist, so this line needs a [clone](../install.md#source-checkout), not `pip install jnwb`.

## The figure

![Synthetic RDM, second-order similarity of two RDMs, and nested cross-validated decoding accuracy](../assets/figures/fig26_ensembles_rdm_decoding.png#only-light)
![Synthetic RDM, second-order similarity of two RDMs, and nested cross-validated decoding accuracy](../assets/figures/fig26_ensembles_rdm_decoding.dark.png#only-dark)

Synthetic: the seeded patterns the tutorial draws, in the same order. Panel A is the RDM of the first pattern set (`jnwb.rdm`). Panel B compares the pair distances of the two sets; its legend gives the second-order Spearman rho (`jnwb.rdm_similarity`). Panel C is the outer-fold accuracy of the nested cross-validated linear SVM (`jnwb.nested_cv_linear_svm`) against its majority baseline; both values are in the legend.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/07_ensembles.py"
```
