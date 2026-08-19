# Joint Relationship & Spectral Analysis (JRSA) Core

This document details the unified Joint Relationship and Spectral Analysis (JRSA) engine, which serves as the core framework for functional connectivity and coupling analyses.

---

## 1. Public API Interface
The engine exposes exactly two public names in `jnwb.jrsa`: the dispatch function `jrsa()` and the structured return class `JRSAResult`.

```python
from jnwb.jrsa import jrsa, JRSAResult
```

### Signature
```python
def jrsa(
    data_x: np.ndarray,
    data_y: np.ndarray,
    metric: str = "correlation",
    fs: float = 1000.0,
    **kwargs
) -> JRSAResult:
```

---

## 2. Supported Metrics & Dispatch
The engine dispatches computations to specialized internal algorithms based on the `metric` parameter:

1. **`correlation`**: Pearson product-moment correlation coefficient between signals.
2. **`coherence`**: Magnitude squared coherence across specified frequency bands:
   $$C_{xy}(f) = \frac{|P_{xy}(f)|^2}{P_{xx}(f) P_{yy}(f)}$$
3. **`mutual_information`**: Shannon mutual information computed on binned spike trains or continuous signals.
4. **`directional_flow`**: Phase-slope index or directional mutual information capturing lead-lag relationships.

---

## 3. Dataclass Return: `JRSAResult`
All dispatched computations return an instance of `JRSAResult` with standardized fields:

* `value`: The computed metric value (e.g., correlation coefficient or mean coherence).
* `statistic`: Parametric test statistic.
* `effect`: Named effect size description.
* `p`: Empirical or parametric p-value.
* `q`: FDR-corrected p-value.
* `df`: Degrees of freedom.
* `ci`: Confidence interval tuple `(low, high)`.
* `metric`: Name of the metric used.
* `axes`: Time/frequency coordinates.

---

## 4. Significance Testing & Permutation Gates
* **Permutation Tests**: Empirical p-values are resolved by shuffling the trial identifiers or phase-scrambling signal vectors to build a null distribution of $N_{\text{shuffles}} \ge 1000$.
* **FDR Correction**: Multi-hypothesis corrections are applied using Benjamini-Hochberg false discovery rate controls across tested channel pairs or frequency bins.
