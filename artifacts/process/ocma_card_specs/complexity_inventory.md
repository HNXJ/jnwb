# OCMA card spec: `complexity_inventory`

STATUS: draft-awaiting-Hamm

Drafted 2026-11-12 at jnwb `92d118ea` (ocma plan decision 5). No card code exists for this spec. Hamm rules it before any code.

| Field | Value |
|---|---|
| id | `complexity_inventory` |
| objective | Card for the inventory of upper bounds on time and peak memory for core primitives (INV-01 to INV-14), with each primitive's algorithm and reference, and the CPU/GPU classification (receipt, sections 2 to 4). The receipt says it is not a measurement. The card is only a pointer to the bounds; a timed check is a separate receipt (receipt, section 2 intro). Card kind: UNKNOWN; "performance" is the nearest schema section (see Flags). |
| reference | Per row, in receipt section 2: Torrence and Compo 1998 (INV-01); Welch 1967 (INV-03, INV-04, INV-10); Welford 1962 (INV-02); Nolte et al. 2004 and 2008 (INV-04, INV-05, INV-10); Granger 1969 and Geweke 1982 (INV-06); Schreiber 2000 (INV-07); Mendoza-Halliday et al. 2024 (INV-08); Pearson and dynamic programming (INV-09); Kriegeskorte et al. 2008 (INV-11, INV-12); scikit-learn LinearSVC documentation (INV-13); ZIP and `.npy` format specifications (INV-14). |
| observable | Asymptotic upper bound on time and on peak memory per primitive, as a function of the symbols in receipt section 1 (`C`, `T`, `F`, `R`, `U`, `S`, `N`, `D`, `K`, `K_seg`, `P`, `E`). No numeric value. Unit: none (order of growth). |
| signal_class | UNKNOWN per row. The receipt does not classify rows by signal. The primitives cover LFP and field signals (`vflip`, `xflip`, `zflip`, `complex_tfr`, `compute_psd`, `wpli`), and non-signal primitives (`rdm`, `rdm_similarity`, `nested_cv_linear_svm`, `stream_npz_array`). No spike primitive is listed. |
| claim_class | None. A bound is not an empirical claim (receipt, header note). |
| dataset | None. The receipt uses symbol definitions (section 1) and no data. |
| operations[] | `complex_tfr`, `TFRAccumulator`, `compute_psd`, `wpli`, `phase_slope_index`, `granger`, `transfer_entropy`, `vflip`, `xflip`, `zflip`, `rdm`, `rdm_similarity`, `nested_cv_linear_svm`, `stream_npz_array` (all quoted in `jnwb/__init__.py`; quoted-string match only). |
| estimand | The stated bound per row, derived from the algorithm named in the row. |
| controls[] | UNKNOWN in the receipt. The receipt points to the timed check: `artifacts/evidence/0.2.6/computational_order.md` section 6, which cites rows here by `INV-` label. That file exists; it was not read (not in this packet's read list). |
| tolerance | UNKNOWN. The receipt's contradiction rule is qualitative: a timed exponent below its bound agrees, one above contradicts (receipt, header note). |
| verdict_rule | Receipt rule: an exponent timed above its bound contradicts the bound; below agrees (receipt, header note). Card-level pass or fail: UNKNOWN. |
| writes[] | Proposed, not in receipt: one `validations` entry, section UNKNOWN until Hamm rules (`section` enum: calibration, performance, frozen, studies, closure). The `fields` value type is string, integer or array, so the bounds would be carried as strings. |
| receipt path | `artifacts/benchmarks/performance/complexity_inventory.md` (tracked; last changed by `5d8ab073`) |
| sha256 | `85525c5fc055bc2abc517838078f8e51de10577fdc5ec91472c79326054906f5` (hashlib, receipt file) |
| recorded_commit | UNKNOWN. The receipt states no commit or version (receipt, whole file). |

## Flags for Hamm (not resolved here)

1. **Not a measurement.** The receipt says a bound is not a measurement (header note). A card would show bounds beside validation cards. Hamm rules whether an inventory is a card at all, or belongs in `docs/` or the evidence tree.
2. **Section.** No schema section fits. `performance` is nearest, but the performance object in `scripts/dashboard/data.schema.json` holds measured values. Hamm rules the section.
3. **Parity wording conflicts.** Section 4 says `band_power` and `_welch_csd_gpu` have "exact SciPy parity". `artifacts/benchmarks/performance/gpu_launch_overhead_0.2.5.md` (section 2) records a pre-existing CPU/CUDA disagreement with SciPy from 2.566e-15 to 4.146e-13 relative. Either the word "exact" carries a tolerance the receipt does not name, or the sentence is wrong. The card cannot state either until the keeper rules it.
4. **Per-row controls are absent.** The receipt cites a timed check (`computational_order.md`, section 6) for every row's exponent. The card cannot state the agreement status of any row without reading that file. Not read here.

## Figure (proposed)

None. The receipt has no figure; a table is the receipt's form.
