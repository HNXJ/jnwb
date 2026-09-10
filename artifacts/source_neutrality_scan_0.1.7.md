# Source-neutrality scan (0.1.7)

Non-blocking residue count after promotion-provenance purge (`rg` on `jnwb/*.py`, 2026-09-10).

## Cleared

| Pattern | `jnwb/` | `tests/` |
|---|---:|---:|
| `PROMOTED 2026` | 0 | 0 |
| `99%-jnwb-sufficiency` | 0 | 0 |
| `promoted 2026-08-23` | 0 | 0 |
| `omission` (string) | 0 | delegation tests only |

Gate 6 scan surface remains PASS.

## Residual study/corpus tokens in `jnwb/` (implementation receipts)

| File | Matches | Nature |
|---|---:|---|
| `jnwb/compression.py` | 11 | NWB path-discovery lessons with subject IDs (V198o, V182o, C31o); not user API contract |
| `jnwb/addressing.py` | 2 | Generic layering note + one cross-session dtype example |
| `jnwb/onset_fitting.py` | 1 | `fit_exponential_onset` docstring historical motivation paragraph |

User-facing module docstrings and `__init__.py` import comments are neutral. Residual tokens are
confined to low-level implementation receipts; optional follow-up if those should move to an
internal design note.

## Receipt

```
python -m pytest tests/ -q  → 641 passed, 15 skipped
python scripts/harness_gate.py  → 12/12 PASS
```
