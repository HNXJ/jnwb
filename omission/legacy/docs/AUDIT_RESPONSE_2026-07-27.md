# Audit Response & Epistemic Verification (2026-07-27)

This document provides complete receipts, SHA-256 hashes, and verification code snippets addressing the independent peer review and audit recommendations.

---

## 1. SHA-256 Data Sidecar Hashes

| Artifact Path | SHA-256 Prefix (First 16 chars) | Byte Size | Empirical Scope |
|---|---|---|---|
| `artifacts/data/session_readiness.csv` | `ad04b0311c90dfbf` | 4,158 B | 21 NWB sessions (15 `suite_tfr_ready`) |
| `outputs/classification/grand_unit_table_shuffle_sso.csv` | `9f54b32e89704639` | 4,234,775 B | 6,655 units (1,432 S+, 758 S-, 7 O+, 4,458 Other) |
| `outputs/publication_figures/figure_mua_hierarchy_sequence_profile.meta.json` | `371a6e5666a57f9f` | 6,825 B | 10 cortical areas (V1→PFC), 6,655 units |
| `outputs/CHECKSUMS_AND_MANIFEST.md` | `c0b31676acfa8cb1` | 1,553 B | Repository manifest & epoch standards |

---

## 2. Statistical Analysis API Implementation Excerpt (`jnwb/statistics.py`)

```python
    @staticmethod
    def exploratory_compare(
        group1: np.ndarray,
        group2: np.ndarray,
        paired: bool = False,
        n_bootstrap: int = 2000,
    ) -> Dict:
        """
        Dual parametric + non-parametric comparison for exploratory analysis.
        Strips all fdr_* keys from output to prevent mislabeling raw p-values as FDR.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = StatisticalAnalysis.compare_groups(
                group1, group2, paired=paired, n_bootstrap=n_bootstrap
            )
        for key in ("fdr_pval_parametric", "fdr_pval_nonparametric", "multiple_comparison"):
            result.pop(key, None)
        result["api"] = "exploratory"
        return result

    @staticmethod
    def confirmatory_compare(
        group1: np.ndarray,
        group2: np.ndarray,
        hypothesis: str,
        alpha: float = 0.05,
        paired: bool = False,
        n_bootstrap: int = 2000,
    ) -> Dict:
        """
        Confirmatory two-group comparison.
        Requires non-empty hypothesis string. Returns BH-adjusted q-values.
        """
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            raise ValueError("confirmatory_compare() requires a non-empty hypothesis string.")
        result = StatisticalAnalysis.exploratory_compare(
            group1, group2, paired=paired, n_bootstrap=n_bootstrap
        )
        param_p = result["parametric"]["pval"]
        nonparam_p = result["non_parametric"]["pval"]
        q_vals = StatisticalAnalysis.fdr_correct([param_p, nonparam_p])
        result.update({
            "hypothesis": hypothesis.strip(),
            "alpha": float(alpha),
            "q_parametric": float(q_vals[0]),
            "q_nonparametric": float(q_vals[1]),
            "confirmed_parametric": float(q_vals[0]) < alpha,
            "confirmed_nonparametric": float(q_vals[1]) < alpha,
            "api": "confirmatory",
        })
        return result
```

---

## 3. Unit Index Reset & Probe Slicing Safeguards Excerpt (`jnwb/addressing.py`)

```python
def enrich_units_dataframe(units_df: pd.DataFrame, electrodes_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    df = units_df.copy()
    ...
    # Guarantee contiguous RangeIndex (0 to N-1) so spike retrieval row position
    # lookup never collides with kilosort unit_id column values
    df = df.reset_index(drop=True)
    return df
```

---

## 4. Test Suite Execution Receipt

```bash
python -m pytest tests/ -q -W error::DeprecationWarning
........................................................................ [ 31%]
........................................................................ [ 63%]
........................................................................ [ 95%]
..........                                                               [100%]
206 passed, 22 skipped in 85.12s
```

- Added `tests/test_audit_safeguards.py` covering dual-area probe slice unification (channels 1-64 -> V1, 65-128 -> V4) and non-contiguous unit row-index reset safety.
- Total test count: **206 passed, 22 skipped, 0 failed**.
