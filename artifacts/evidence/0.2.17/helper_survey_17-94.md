# Private helpers of the function splits: one definition each (17-94)

Baseline e9b0f358. Scope: every module-level `def _...` in `jnwb/laminar/_xflip.py`, `_zflip.py`,
`_vflip.py`, `jnwb/jrsa/__init__.py` and `jnwb/connectivity/_psi.py` (the item's `_psi.py`; there is
no `jnwb/spectral/_psi.py`). Reproduce: `python artifacts/evidence/0.2.17/survey_helpers_17-94.py .`
from the repository root.

Method: each helper's body, docstring dropped and parameters renamed positionally, is compared by
AST dump against all 1060 function definitions in `jnwb/` (exact), and again with string constants
and names erased (loose: same structure, other messages or names). Known positive and negatives of
the comparator: a parameter-renamed copy matches exact; `x + y` against `x - y` does not; two
raises differing only in message match loose and not exact. Candidates by name, by call-set overlap
(Jaccard >= 0.6, same arity) and by grep for the operation (Welch segmentation, coherency, band
bins, surrogates, run finding, rescaling, phase slope) were then read.

| File | Helpers | Exact matches | Loose matches |
|---|---|---|---|
| `jnwb/laminar/_xflip.py` | 33 | 0 | 0 |
| `jnwb/laminar/_zflip.py` | 21 | 0 | 0 |
| `jnwb/laminar/_vflip.py` | 14 | 0 | 0 |
| `jnwb/jrsa/__init__.py` | 13 | 0 | 0 |
| `jnwb/connectivity/_psi.py` | 23 | 0 | 0 |
| Total | 104 | 0 | 0 |

Candidates read and found distinct:

| Helper | Candidate | Difference |
|---|---|---|
| `_xflip._window_rows` | `_zflip._window_rows` | Recorded in the item: TypeError against ValueError on a malformed pair, zflip refuses fewer than 3 rows, `np.bool_` and messages differ |
| `_zflip._phase_slope` | `jrsa/_metrics._phase_slope` | R^2 and delay of a linear fit to the unwrapped cross-spectral phase, against a PSI wrapper over `phase_slope_index` |
| `_psi._welch_segments` | `spectral/_coupling.welch_segment_count`, `_csd_spectra_cpu` | Returns the segments themselves, per trial, refusing zero; the others count segments (0 allowed) or call `scipy.signal` |
| `_psi._coherency` | `spectral/_coupling.imaginary_coherency` | Per-segment FFT average returning complex coherency per bin; the other is a public estimator on raw traces |
| `_psi._surrogate_null` | `connectivity/_common._surrogate_source` | Calls it; builds the per-band null |
| `_xflip._surrogate_phase_randomize` | `connectivity/_common._surrogate_source` | Fourier phase randomization per channel, against trial permutation or circular shift |
| `_vflip._unit_range` | none | Only min-max rescaling with a 1e-12 floor in `jnwb/` |
| `_zflip._linear_to_roundoff` | none | Only second-difference linearity test in `jnwb/` |
| `_xflip._refuse_short_window`, `_zflip._require_accepted_vflip2`, `_check_*` validators | `_bins.check_bin_label`, `_units.resolve_unit_alias`, `spectral/_common._require_*` | Call-set overlap only; different arguments, accepted sets and messages |

Result: 104 surveyed, 0 merged, 104 distinct. No source changed.
