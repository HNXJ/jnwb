# Independent zero-based audit — final closure (`dev@fca1460` + RG)

**Discovery SHA:** `fca146003d6bcaf60fea9401269ba2c1b2817a20`  
**Method:** Eight partitions, mechanical search + semantic inspection + discriminating probes.  
**Constraint:** No use of prior audit checklist or consumed todo items as discovery input.  
**RG:** Material defects repaired in working tree (post-discovery); partitions 1–3 and 5 re-verified.

---

## Verdict

| Question | Answer |
|---|---|
| Material defects at discovery (`fca1460`)? | **Yes** — 14 confirmed (see below) |
| Material defects after RG (working tree)? | **None known** among repaired classes |
| Supports “no known material defect”? | **Conditional yes** — pending Hamm review of RG diff + full release_gate receipt |
| 100/100 closure? | **Not yet** — version still `0.1.6`; justified debt remains |

---

## Partition 1 — Scientific / numerical semantics

| ID | Finding | Class | Evidence | RG |
|---|---|---|---|---|
| F1-1 | `granger` rejected valid minimal-DoF VAR (`n_obs > n_params + 1`) | **material** | Probe: `fit_var_bivariate(n=20,order=6)` OK; `granger(order=6)` raised | **fixed** |
| F1-2 | `fit_var_bivariate` / `granger_causality` returned `(1.0,1.0)` on short series | **material** | Probe: `n=8,order=5` → zeros, no error | **fixed** |
| F1-3 | `UnitAnalyzer.psth` bin count ≠ `bin_spikes` (`int` vs `round`) | **material** | Probe: 85 vs 86 bins | **fixed** |
| F1-4 | `compare_groups(paired=True)` with one pair reported `paired_t_test` | **material** | Probe: `df=0`, `p=1.0` | **fixed** |
| F1-5 | `spike_mutual_information([])` → `0.0` | **material** | Probe | **fixed** |
| F1-6 | `band_power` out-of-band → `-inf` dB | **material** | Probe | **fixed** |
| F1-7 | jRSA CuPy `_bootstrap` ignored caller `rng` | **material** | Code path `cp.random.randint` | **fixed** |
| F1-8 | jRSA `align='dtw'` silent fallback without `dtw-python` | **justified debt** | Warns then downsample-resamples | open |
| F1-9 | Monte Carlo `(b+1)/(B+1)` in statistics/connectivity/jRSA `_p_from_null` | **clean** | Grep + prior probes | — |
| F1-10 | No `np.random.seed` in `jnwb/` | **clean** | Grep | — |

---

## Partition 2 — API / estimator identity

| ID | Finding | Class | Evidence |
|---|---|---|---|
| F2-1 | jRSA legacy `metric="granger"` / `"transfer_entropy"` blocked with migration | **clean** | `ValueError` + renamed metrics |
| F2-2 | `granger_ssr_ftest` ≠ `granger` (F-stat vs log variance ratio) | **documented collision** | Probes differ; docs/03 disambiguates |
| F2-3 | `transfer_entropy_histogram_nats` ≠ `transfer_entropy` (nats vs bits) | **documented collision** | Probes + test |
| F2-4 | `granger_causality` deprecated, still in `__all__` | **justified debt** | `DeprecationWarning` on call |
| F2-5 | `normalize` homonym (jRSA min-max vs `band_power` dB) | **justified debt** | Different modules; document at call site |
| F2-6 | `__all__` 111 symbols resolvable | **clean** | Gate 9 |

---

## Partition 3 — README / docs / examples / API reference

| ID | Finding | Class | Evidence | RG |
|---|---|---|---|---|
| F3-1 | `docs/index.md`, `docs/04`, `AGENTS.md` §10 `band_power` examples failed at default | **material** | Runtime `ValueError` | **fixed** |
| F3-2 | `docs/03` documented `.similarity`/`.pval`/`.rdm` | **material** | Runtime: `.value`/`.p` only | **fixed** |
| F3-3 | `docs/10` promised MCP appendix in `docs/11` | **material** | Grep: no MCP in doc 11 | **fixed** |
| F3-4 | Duplicate quickstart tours (script vs markdown) | **optional** | Explicitly labeled in quickstart.md | — |
| F3-5 | `docs/api.md` ↔ `__all__` | **clean** | 111/111, generator gate | — |
| F3-6 | `examples/quickstart_jnwb.py` `omission/` pointer | **optional** | Gitignored downstream project | — |

---

## Partition 4 — Tests / gates / false-PASS risks

| ID | Finding | Class | Evidence |
|---|---|---|---|
| F4-1 | No `except: pass` in tests | **clean** | Grep |
| F4-2 | `test_jnwb_core.py` smoke `isinstance(dict)` only | **optional** | Weak but not swallowing |
| F4-3 | Gate 3 skips unparseable test files (`except: continue`) | **justified debt** | Documented bypass |
| F4-4 | Four harness helpers not in `run_full_preflight` | **justified debt** | Adversarial tests only |
| F4-5 | `importorskip` MCP/notebooks off `[test]` extra | **justified debt** | CI installs `[test]` |
| F4-6 | `release_gate.py` not in pytest suite | **justified debt** | Manual pre-tag step |

---

## Partition 5 — Packaging / install / release

| ID | Finding | Class | Evidence | RG |
|---|---|---|---|---|
| F5-1 | Sdist shipped full `tests/` (46 files); wheel clean | **material** | `tarfile` probe | **fixed** (`MANIFEST.in`) |
| F5-2 | Forbidden-manifest checks omitted `tests/` | **material** | `release_gate.py`, CI | **fixed** |
| F5-3 | `release_gate.py` not in CI | **justified debt** | CONTRIBUTING policy |
| F5-4 | CI wheel smoke thinner than release_gate Step 7 | **justified debt** | By design |
| F5-5 | PyPI policy (tag ≠ publish; Release published) | **clean** | `workflow.yml` + tests |

---

## Partition 6 — Dataset boundary / provenance

| ID | Finding | Class | Evidence |
|---|---|---|---|
| F6-1 | Gate 6 scan surface | **clean** | 0 violations / 63 files |
| F6-2 | Queried tokens `2.8x`, `rho=-0.02`, `S+/S++` | **clean** | Absent from `jnwb/` |
| F6-3 | Subject IDs in `compression.py` docstring | **optional** | Docstring-only receipts |
| F6-4 | “Promoted from …” provenance strings | **optional** | Outside Gate 6 list |
| F6-5 | Tripwire #1 on public return paths | **clean** | No hardcoded empirical outputs |

---

## Partition 7 — Architecture / dependencies / maintenance

| ID | Finding | Class | Evidence |
|---|---|---|---|
| F7-1 | Frozen boundary (`omission` imports) | **clean** | 0 imports |
| F7-2 | `nwb_io` read boundary scoped | **clean** | Tests present |
| F7-3 | Partial lazy imports (scipy/pandas eager) | **justified debt** | Import profile |
| F7-4 | `__version__` 0.1.6 vs CHANGELOG 0.1.7 unreleased | **expected** | No bump per instruction |
| F7-5 | Dual Granger APIs during deprecation window | **justified debt** | Policy decision |

---

## Partition 8 — Harness / skills / instructions

| ID | Finding | Class | Evidence | RG |
|---|---|---|---|---|
| F8-1 | `harness_gate.py` module header gates 9–12 ≠ implementation | **material** (instruction drift) | Header vs docstrings | **fixed** |
| F8-2 | `_audit_dist_build/` failed Gate 4 after local builds | **material** (hygiene) | Adversarial test | **fixed** (ephemeral allowlist) |
| F8-3 | `jnwb-lfp-spectral` skill omits `band_power` routing | **optional** | Skill coverage gap |
| F8-4 | RNG policy (`rng`) vs connectivity `seed=` APIs | **justified debt** | API surface choice |

---

## Post-RG verification receipts

```text
git rev-parse HEAD          → fca1460 (discovery); RG uncommitted in working tree
python -m pytest tests/ -q  → 676 passed (after RG)
python scripts/harness_gate.py → 12/12 PASS (after RG)
mkdocs build --strict       → PASS (after RG)
sdist tests/ count          → 0 (after MANIFEST.in)
_audit_dist/ _audit_dist2/  → deleted (clean tree)
```

`python scripts/release_gate.py` — not re-run in this session after RG (prior run on pre-RG tree: PASS at `fca1460` parent fixes). **Recommend re-run before 0.1.7 seal.**

---

## Remaining justified debt / optional improvements

- jRSA DTW alignment silent fallback (`align='dtw'`).
- Deprecated `granger_causality` until removal window ends.
- Subject-ID / promotion provenance neutralization in docstrings.
- Skill routing gaps (`band_power` in `jnwb-lfp-spectral`).
- Gate 3 parse-fail continue; helpers outside preflight.
- Property-based estimator coverage (pre-1.0 stack item).
- Four planned notebooks (unversioned stack).
