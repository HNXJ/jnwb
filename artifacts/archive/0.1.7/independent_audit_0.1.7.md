# Independent zero-based audit (0.1.7)

**SHA:** `2c69640b58696a99e390ae7460d6050147331d2e` (`dev`)  
**Method:** Eight partitions reviewed independently; `artifacts/todo_stack.md` consulted only after discovery.  
**Receipts at audit time:** `python scripts/harness_gate.py` → 12/12 PASS (clean tree); targeted probes below.

---

## Summary

| Partition | Confirmed defects | Justified debt | Optional improvement | False positive |
|---|---:|---:|---:|---:|
| 1 Scientific/numerical | 11 | 4 | 2 | 2 |
| 2 API/code | 0 | 2 | 2 | 1 |
| 3 Documentation | 3 | 0 | 4 | 1 |
| 4 Tests/gates | 2 | 1 | 2 | 2 |
| 5 Packaging/release | 0 | 1 | 3 | 2 |
| 6 Boundary/provenance | 2 | 1 | 4 | 3 |
| 7 Architecture | 0 | 3 | 1 | 2 |
| 8 Harness/skills | 2 | 0 | 4 | 1 |

**Material defect count (confirmed): 20** — see reconciliation in `artifacts/todo_stack.md`.

**Stop for Hamm (consequential API/scientific choice):** S1-8, S1-9, A7-5 (jrsa metric identity; dual Granger APIs).

---

## Partition 1 — Scientific/numerical semantics

### S1-1 `StatisticalAnalysis.permutation_test` omits +1 Monte Carlo correction
- **Classification:** confirmed defect
- **Evidence:** `jnwb/statistics.py:749` — `pval = count / n_permutations`; probe: `pval=0.0`, exact `(1+k)/(B+1)=0.01` for same seed/draw.
- **Consequence:** Anti-conservative p-values; can report 0 when minimum is `1/(B+1)`.
- **Smallest repair:** `(1 + k) / (n_permutations + 1)`.
- **Verification:** Regression test with fixed RNG where exactly one null exceeds observed.

### S1-2 `shuffle_r2_ci` uses uncorrected empirical p-value
- **Classification:** confirmed defect
- **Evidence:** `statistics.py:316-317` — `p_val = mean(null >= r2_obs)` with floor only when `p==0`.
- **Consequence:** Same anti-conservative bias as S1-1; inconsistent with `shuffle_pvalue_*`.
- **Smallest repair:** `(1 + sum(null >= r2_obs)) / (n_shuffle + 1)`.
- **Verification:** Perfect-rank case yields `p_val == 1/(n_shuffle+1)`.

### S1-3 `compare_groups(paired=True)` silent independent fallback
- **Classification:** confirmed defect
- **Evidence:** `statistics.py:502-563`; probe: `compare_groups([1,2,3,4],[1,2,3], paired=True)` → `independent_t_test`.
- **Consequence:** Paired interpretation with unpaired test; no warning flag.
- **Smallest repair:** `ValueError` when `paired=True` and valid lengths differ.
- **Verification:** Length mismatch raises; equal lengths still use `paired_t_test`.

### S1-4 `cross_modal_comparison` lacks axis contract
- **Classification:** confirmed defect
- **Evidence:** `statistics.py:922-937` — hard-coded `mean(axis=0)` / `mean(axis=-1)`; probe: permuted TFR layout yields wrong `n_samples`.
- **Consequence:** Silent wrong correlation/lag on non-canonical layouts.
- **Smallest repair:** Validate `(freq, time, trials)` / `(time, trials)` or require explicit axes.
- **Verification:** Canonical layout passes; `(trials, time, freq)` raises.

### S1-5 `spike_mutual_information` bin grid ≠ `bin_spikes`
- **Classification:** confirmed defect
- **Evidence:** `connectivity.py:113-118` uses `int((t_end-t_start)/bin_sec)`; `bin_spikes:717` uses `round`.
- **Consequence:** MI on different temporal grid than library binning primitive.
- **Smallest repair:** Delegate MI bin edges to `bin_spikes`.
- **Verification:** `n_bins` always matches for shared `(window, bin_size_ms)`.

### S1-6 `granger(order="auto")` ≠ `select_optimal_lag` IC convention
- **Classification:** confirmed defect
- **Evidence:** `connectivity.py:985-994` RSS/`n_obs` vs `_info_criterion` RSS/(N−p) at `282-323`.
- **Consequence:** Auto lag order differs by entry point.
- **Smallest repair:** Unify IC computation in `_select_order`.
- **Verification:** `select_optimal_lag(...) == granger(..., order='auto').params['order_x_to_y']` on fixed series.

### S1-7 `granger_spectral` assigns one surrogate p to all bands
- **Classification:** confirmed defect
- **Evidence:** `connectivity.py:1322-1326` — identical `p_surrogate` per band.
- **Consequence:** Band-level significance not band-specific.
- **Smallest repair:** Band-masked null means and per-band `(1+k)/(B+1)`.
- **Verification:** GC injected in one band only → other bands have higher p.

### S1-8 `jrsa(metric="granger")` ≠ `connectivity.granger` **⚠ Hamm**
- **Classification:** confirmed defect
- **Evidence:** `jrsa.py:1285-1323` (statsmodels F) vs `connectivity.py:859+` (log variance ratio); probe: `jrsa=0.78`, `granger=-0.0024` on same arrays.
- **Consequence:** Same metric name, different estimand/units/trial pooling.
- **Smallest repair (choices):** (a) delegate `_granger` to `connectivity.granger`, (b) rename to `granger_f_test`, (c) remove metric.
- **Verification:** Unified path: values match within tolerance.

### S1-9 `jrsa(metric="transfer_entropy")` ≠ `connectivity.transfer_entropy` **⚠ Hamm**
- **Classification:** confirmed defect
- **Evidence:** `jrsa.py:1329-1366` (nats, ravel histogram) vs `connectivity.py:1732+` (bits, trial-aware).
- **Consequence:** Incomparable TE magnitudes across APIs.
- **Smallest repair:** Delegate or remove jrsa TE metric.
- **Verification:** Values match on fixed seed/shape.

### S1-10 `band_power(normalize=True, baseline=None)` is a no-op
- **Classification:** confirmed defect
- **Evidence:** `spectral.py:633-697`; probe: `normalize=True, baseline=None` identical to `normalize=False`.
- **Consequence:** Callers expect dB normalization; get linear power silently.
- **Smallest repair:** `ValueError` when `normalize=True` and `baseline is None`.
- **Verification:** Raises; with baseline returns dB.

### S1-11 `jrsa` permutation p-values omit +1; GPU permutations unseeded
- **Classification:** confirmed defect
- **Evidence:** `jrsa.py:760-773`, `727-741`.
- **Consequence:** Anti-conservative jrsa inference; GPU path non-reproducible.
- **Smallest repair:** `(1+k)/(n+1)`; seed CuPy path from `Generator`.
- **Verification:** CPU/GPU identical null/p for fixed `random_state` when CUDA available.

### S1-12 `transfer_entropy(estimator="symbolic")` misreports `n_times`
- **Classification:** confirmed defect
- **Evidence:** `connectivity.py:1843-1905` — embedding shortens time; `n_times` stays full length.
- **Consequence:** Provenance field wrong for surrogate sufficiency.
- **Smallest repair:** Set `n_times` to embedded length.
- **Verification:** `n_times == x.shape[1] - symbolic_order + 1`.

### S1-13–S1-18 (justified debt / optional / clean)
- Population std in `compute_response_metrics` — optional improvement.
- `rate_in_window` vs `fires_in_window` invalid-window inconsistency — optional improvement.
- `classify_response_significance` Gaussian heuristic — justified debt.
- CPU/GPU Welch/coherence path differences — justified debt (`device_used` recorded).
- `phase_locking_index` bias — justified debt (PPC documented).
- `nested_cv_linear_svm` fixed `random_state=42` — justified debt.
- TFR / `aggregate_to_db` / artifact repair / permutation primitive — clean (false positive for defects).

---

## Partition 2 — API/code consistency

- **A2-1** API generator types constants as `function` — optional improvement (`generate_api_md.py`).
- **A2-2** Stale unused imports in `__init__.py` — optional improvement.
- **A2-3** `mcp_server` needs `mcp` extra — justified debt (documented in `install.md`).
- **A2-4** `gpu_pca` module-internal — justified debt.
- **A2-5** Gate 5 weaker than Gate 9 — false positive (Gate 9 is authority).

Mechanical health: 111/111 `__all__` symbols resolve; Gate 9 PASS.

---

## Partition 3 — Documentation/usability

### D3-1 Quickstart narrative ≠ runnable script/figure
- **Classification:** confirmed defect
- **Evidence:** `docs/quickstart.md` steps: TFR → PSI → jRSA; `examples/quickstart_jnwb.py` `PANELS`: band_power → permute_labels → granger → nested_cv_linear_svm. Both claim “Canonical 6-Panel Architecture”.
- **Consequence:** Readers and figure disagree.
- **Smallest repair:** Align markdown to script (script is smoke-tested + generates figure).
- **Verification:** Panel API strings in script appear in `quickstart.md`; `python examples/quickstart_jnwb.py` exit 0.

### D3-2 `docs/10` phantom test files
- **Classification:** confirmed defect
- **Evidence:** `docs/10_extending_jnwb_and_verification.md:44` cites `test_skill_tree_consolidation.py` (absent); `test_batch_a_regressions.py` (absent).
- **Consequence:** Contributors run nonexistent tests.
- **Smallest repair:** Point to `tests/test_skills_validation.py`, harness gates, actual regression modules.
- **Verification:** `rg test_skill_tree_consolidation` → 0.

### D3-3 `docs/10` uses `omission/` as canonical facade pattern
- **Classification:** confirmed defect (boundary + docs)
- **Evidence:** `docs/10:15-16` — published on MkDocs nav.
- **Consequence:** RTD teaches a specific downstream project name.
- **Smallest repair:** Neutral placeholders (`my_project/`).
- **Verification:** `rg "omission" docs/` → 0.

### D3-4–D3-7 optional: `common_mistakes` undefined `spikes_list`, README NWB block not smoke-tested, duplicate `api.md` nav, image link coverage — optional improvements.

### D3-8 Executable param/return names in tested doc blocks — false positive (aligned at this SHA).

---

## Partition 4 — Tests/gates/reliability

### T4-1 `test_jnwb_core.py` broad `except Exception: pass`
- **Classification:** confirmed defect
- **Evidence:** Five sites ~L170-283.
- **Consequence:** Real regressions register as PASS.
- **Smallest repair:** `pytest.raises` for expected failures.
- **Verification:** Introduced bug fails test.

### T4-2 Ephemeral `_audit_dist*` breaks Gate 4 on local trees
- **Classification:** confirmed defect (gate reliability)
- **Evidence:** `harness_gate.py` `EPHEMERAL_ROOT_DIRS` omits `_audit_dist`; dirs present on audit machine.
- **Consequence:** `test_real_repository_passes_all_harness_gates` false FAIL after wheel audits.
- **Smallest repair:** Add `_audit_dist`, `_audit_dist2` to allowlist.
- **Verification:** Gate 4 PASS with dirs present.

### T4-3–T4-6 optional/mixed: missing quickstart doc↔script adversarial fixture; notebook skip on minimal install; HDMF subprocess pattern acceptable; broad suite otherwise strong.

---

## Partition 5 — Packaging/install/release

- **P5-1** Python 3.13 classifier without CI matrix — justified debt (Gate 8 policy: floor + head).
- **P5-2** `release_gate.py` not in CI — optional improvement.
- **P5-3** `jnwb[all]` includes CUDA cupy — optional improvement.
- **P5-4** CONTRIBUTING version bump mentions static pyproject version — optional improvement.
- **P5-5/6** GitHub Release before PyPI; torch/gpu extras separate — false positives (verified).

---

## Partition 6 — Boundary/provenance/no-trace

### B6-1 Hardcoded empirical values in `jnwb/` docstrings (tripwire #1)
- **Classification:** confirmed defect
- **Evidence:** `compression.py:12` (`~2.8x`, session ratios); `onset_fitting.py:79-82` (`rho=-0.02, p=0.98`, `S+/S++`).
- **Consequence:** User-facing docstrings carry corpus-specific numbers not computed at read time; violates CLAUDE tripwire #1 spirit.
- **Smallest repair:** Algorithmic description only; move receipts to `artifacts/`.
- **Verification:** `rg "2\\.8x|rho=-0\\.98" jnwb/` → empty.

### B6-2 Subject/session IDs in implementation receipts
- **Classification:** optional improvement (audit overrides prior “optional only” stack framing)
- **Evidence:** `compression.py` V198o/V182o/C31o; `addressing.py:240-241`.
- **Consequence:** Generic library reads as one-corpus tool; Gate 6 does not scan subject IDs.
- **Smallest repair:** Generalize patterns without subject labels.
- **Verification:** `rg "V198o|V182o|C31o" jnwb/` → empty.

### B6-3 Gate 6 scan surface narrower than AGENTS §4 prose — optional improvement (policy alignment).
### B6-4 `compression.py` example `import jnwb as oa` — optional improvement.
### B6-5–B6-10 clean: no agent traces in `jnwb/`; no omission imports; `OMISSION_*_DIR` deprecated shim accepted.

---

## Partition 7 — Architecture/maintenance

- **A7-1** Partial lazy-import migration — justified debt (0.1.6 CHANGELOG vs eager connectivity/spectral).
- **A7-2** `nwb_io` read boundary — sound (pass).
- **A7-3** `compression.py` h5py vs `read_nwb` split — justified debt (documented).
- **A7-4** `jrsa` default `n_jobs=-1` vs `parallel_map` default 1 — justified debt (skill documents).
- **A7-5** Dual `granger` / `granger_causality` — justified debt pending deprecation **⚠ Hamm**.
- **A7-6** `_backend`/`_parallel` centralization — pass.
- **A7-7** Dormant `PROTECTED_PATHS` omission entries — optional improvement.

---

## Partition 8 — Harness/skills authority

### H8-1 `harness_gate.py` header lists 8 gates only
- **Classification:** confirmed defect
- **Evidence:** File header L4-12 vs `run_full_preflight` gates 1–12.
- **Consequence:** Script header contradicts AGENTS/CONTRIBUTING.
- **Smallest repair:** Update header to match `run_full_preflight`.
- **Verification:** Manual read / optional docstring test.

### H8-2 Duplicate/stale extending docs (`docs/10` vs `docs/11`)
- **Classification:** confirmed defect
- **Evidence:** MkDocs nav lists both; CONTRIBUTING points only to `11`; `10` stale (D3-2, D3-3).
- **Consequence:** Two conflicting extending entry points.
- **Smallest repair:** Merge or demote `10` to pointer → `11`.
- **Verification:** Single canonical extending page; `mkdocs build --strict`.

### H8-3–H8-7 optional: CLAUDE external skills note, frozen-boundary test cites removed CLAUDE policy, AGENTS Gate 6 wording, CONTRIBUTING skill-load line — optional improvements.
### H8-8 Pre-push four-check order — pass.

---

## Independent probe receipt (audit author)

```
permutation_test pval 0.0  vs exact (1+k)/(B+1) 0.01
compare_groups paired=True length mismatch → independent_t_test
band_power normalize=True,baseline=None equals normalize=False → True
jrsa granger 0.779966  vs connectivity.granger -0.002408
```

---

## Reconciliation note

Findings above were mapped to `artifacts/todo_stack.md` **after** discovery. The prior optional receipt-cleanup item is **upgraded to required** for B6-1 only (tripwire); B6-2 remains optional neutralization.

Second-audit placeholder removed from stack; replaced by this artifact.
