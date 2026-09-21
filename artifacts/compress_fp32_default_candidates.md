# `compress_fp32` default-selection candidates (06-13)

The table 06-13 requires before its ruling. Every cell is the outcome of executing the
selection, not of reading the selector. **This file does not rule and recommends nothing.**

- Baseline: `c0d53a4751ba3e8a12a331ca40dcb2aae2a5af4b`, worktree clean.
- Subject: `jnwb/compression.py`, sha256[:16] `da0424b6337e4512`.
- Every probe asserts `jnwb.__file__` resolves under the worktree and prints it:
  `C:\workspace\jnwb\.claude\worktrees\agent-ac2155c8a70df934f\jnwb\__init__.py`.
- The 22-session corpus on `D:` was not read. Cells that need it are marked `UNRESOLVED`.
- Probes: `p_candidates.py`, `p_endtoend.py`, `p_mechanism.py`, `p_contract.py`, `p_stamp.py`,
  in the session scratchpad; JSON under `work/`.

## 0. Result first

**No candidate is semantics-preserving against the status quo.** C1, C2 and C3 add datasets to
the irreversible cast; C4, C5 and C6 remove datasets the status quo casts. The governing
principle ruled 2026-09-19 — irreversible lossy selection must be explicit where no generic
semantic rule exists — therefore finds no generic rule to defer to. That is the fact the ruling
turns on, and it is now measured at this baseline rather than carried.

Two things changed since 06-13's table was written, and both make the candidates worse:

| Landed | Effect on the candidates |
|---|---|
| 06-79 (`_chunk_shape` follows rank) | C2 and C3 used to abort on a 1-D float64 series with `ValueError: 'chunks' must have same rank as dataset shape`. They now run to completion and **silently downcast it**. A loud refusal became a silent irreversible cast. |
| 06-78 (the contract has a test) | `tests/test_compression.py` is now 61 tests, not 15. The status quo passes 61. **Every other candidate fails**, minimum 3 (C3), maximum 21 (C6). |

## 1. Measurement populations

The repository fixture carries no behavioural series and no arbitrary acquisition series, so
four of the table's columns are unmeasurable on it alone. The extension is declared here, not
smuggled into a result.

| Population | Contents | Built by |
|---|---|---|
| `FIXT` | Exactly the datasets `tests/test_compression.py` builds: `acquisition/probe_0_lfp/data` (2-D f64), the nested `probe_0_lfp/probe_0_lfp_data/data`, `acquisition/probe_1_muae/data`, `probe_0_lfp/timestamps`, `spike_train` (2-D **int16**), `convolved_spike_train` (2-D f64) | `build_fixt`, from lines 49-96 and 421-425 of the test file |
| `FIXT+` | `FIXT` plus `acquisition/eye_position/data` (2-D f64), `acquisition/photodiode/data` (**1-D** f64), `acquisition/my_custom_series/data` (2-D f64), `analysis/derived_metric/data` (2-D f64) | `build_fixt_plus(typed=False)` |
| `FIXT+typed` | `FIXT+` with `neurodata_type` attributes and `electrodes` siblings populated | `build_fixt_plus(typed=True)` |
| `STD-ES` | Standard NWB, `ElectricalSeries` in `acquisition/`, `processing/` empty | `jnwb.testing.nwb_fixtures`, `canonical_co_resident_options()` |
| `STD-PROC` | Standard NWB with a populated `ecephys` processing module | `jnwb.testing.nwb_fixtures`, `processing_lfp_options()` |

`photodiode` is 1-D deliberately: it is what tests whether 06-79 changed which datasets a
candidate can reach.

## 2. The required table

Measured end to end on `FIXT+typed`, the only population carrying every column. Each cell is
the destination dtype after `compress_fp32` ran with that candidate installed as the selector.
Where a candidate behaves differently on a population without `neurodata_type` attributes, the
divergence is given in the cell.

| Candidate policy | LFP | MUAe | spikes | behavioural series | arbitrary acquisition | information newly lost | previously compressed, now preserved |
|---|---|---|---|---|---|---|---|
| **C0** status quo `^acquisition/(probe_\d+_(?:lfp\|muae))(?:/\1_data)?/data$` | **DOWNCAST** f64→f32, err 7.584658e-06 (flat) and 7.355104e-06 (nested) | **DOWNCAST** f64→f32, err 7.613257e-06 | `spike_train` **preserved** int16; `convolved` **preserved** f64, bit-identical | `eye_position` **preserved** f64; `photodiode` **preserved** f64 | `my_custom_series` **preserved** f64; `analysis/derived_metric` **preserved** f64 | — (reference row) | — (reference row) |
| **C1** float64 and 2-D | **DOWNCAST** (flat and nested) | **DOWNCAST** | `spike_train` **preserved** int16 (dtype gate). `convolved` **selected** but written back f64 bit-identical by `CONVOLVED_PATH` — carries a **false stamp**, §5 | `eye_position` **DOWNCAST**, err 9.000288e-07. `photodiode` **preserved** (1-D, rank gate) | `my_custom_series` **DOWNCAST**. `analysis/derived_metric` **DOWNCAST** (outside `acquisition/`) | `/acquisition/eye_position/data`, `/acquisition/my_custom_series/data`, `/analysis/derived_metric/data` | none |
| **C2** float64 and basename `data` | **DOWNCAST** (flat and nested) | **DOWNCAST** | as C1: `spike_train` preserved int16; `convolved` selected, restored, **false stamp** | `eye_position` **DOWNCAST**. **`photodiode` DOWNCAST**, err 1.184242e-07, chunks `(1000,)` — *this is new since 06-79; it used to abort* | `my_custom_series` **DOWNCAST**. `analysis/derived_metric` **DOWNCAST** | `/acquisition/eye_position/data`, `/acquisition/photodiode/data`, `/acquisition/my_custom_series/data`, `/analysis/derived_metric/data` | none |
| **C3** float64, under `acquisition/`, basename `data` | **DOWNCAST** (flat and nested) | **DOWNCAST** | both **preserved**, neither selected, no stamp | `eye_position` **DOWNCAST**. **`photodiode` DOWNCAST** — *new since 06-79* | `my_custom_series` **DOWNCAST**. `analysis/derived_metric` **preserved** (outside `acquisition/`) | `/acquisition/eye_position/data`, `/acquisition/photodiode/data`, `/acquisition/my_custom_series/data` | none |
| **C4** parent `neurodata_type == ElectricalSeries` | `FIXT`/`FIXT+`: **selects nothing** (0 attrs) → **preserved**. `FIXT+typed`: flat **DOWNCAST**, nested **preserved**. `STD-ES`: selects `acquisition/probe_0_lfp/data`, already f32 | same as LFP | **both selected** on `FIXT+typed`, both written back at source dtype by the constants: `spike_train` int16, `convolved` f64 bit-identical. Both carry a **false stamp**, §5 | **preserved** (`SpatialSeries` / `TimeSeries`) | **preserved** (`TimeSeries`) | nothing is in fact lost: the two it adds are both restored by a constant | `FIXT`/`FIXT+`: **all three** — `/acquisition/probe_0_lfp/data`, `/acquisition/probe_0_lfp/probe_0_lfp_data/data`, `/acquisition/probe_1_muae/data`. `FIXT+typed`: the nested path only |
| **C5** float64, basename `data`, `electrodes` sibling *(added, §3)* | `FIXT`/`FIXT+`: **selects nothing** → **preserved**. `FIXT+typed`: flat **DOWNCAST**, nested **preserved**. `STD-ES`: selects nothing, blocked by the dtype gate — the sibling is present, the data is already f32 | same as LFP | both **preserved**, neither selected | **preserved** | **preserved** | none | `FIXT`/`FIXT+`: **all three**. `FIXT+typed`: the nested path only |
| **C6** float64, basename `data`, cast measured bit-exact *(added, §3)* | **selects nothing** on every population → **preserved** | **preserved** | both **preserved** | **preserved** | **preserved** | none — by construction it never loses a bit | **all three**: `/acquisition/probe_0_lfp/data`, `/acquisition/probe_0_lfp/probe_0_lfp_data/data`, `/acquisition/probe_1_muae/data` |

Real-corpus cells for every row: `UNRESOLVED (real corpus, not measurable here)`. What would
settle them: running the same predicates over the 22 sessions named in
`artifacts/data/corpus_manifest.json` and recording on-disk dtype in bytes per element. A prior
packet did this at baseline `577847f2` and its numbers are in
`artifacts/compress_fp32_policy.md`; those are **not** re-measured here and predate 06-78 and
06-79, both of which changed candidate behaviour.

### The nested-layout cell for C4 and C5 depends on where the attribute sits

On `FIXT+typed` I placed `neurodata_type` on the outer `probe_0_lfp` group, so the inner
`probe_0_lfp_data/data` is not selected. `STD-PROC`, written by pynwb, shows the real
convention: the **inner** object carries the type (`processing/ecephys/LFP/probe_0_lfp_data`).
A nested file written by pynwb would therefore have C4 select the inner path and not the outer.
This cell is a property of the fixture's construction, not a finding about NWB, and is marked
as such rather than reported as a measurement.

## 3. The two added candidates, and why they are defensible

**C5 — `electrodes` sibling.** Every NWB `ElectricalSeries` carries an `electrodes`
DynamicTableRegion as a sibling dataset. Measured on the pynwb fixture:
`acquisition/probe_0_lfp members : ['data', 'electrodes', 'starting_time']`. It marks a series
bound to the electrode table without depending on `neurodata_type` having been written, and it
survives renaming the series — which is exactly the weakness C4 has on files that omit the
attribute. Measured outcome: it inherits C4's defect anyway. On `FIXT`/`FIXT+` it selects
nothing, so it drops all three datasets the status quo casts.

**C6 — cast measured bit-exact.** The only candidate that can be semantics-preserving in the
sense the governing principle uses, because it reads the values and selects only where the
float32 round trip is lossless. Measured outcome: **it selects nothing on any fixture**, so it
compresses nothing. Its costs are that selection becomes data-dependent — two structurally
identical files convert differently — and that it reads every value before deciding.

## 4. Exact selected sets, so the differences are checkable

Set differences, not summaries. Status quo on all three h5py populations selects:

```
/acquisition/probe_0_lfp/data
/acquisition/probe_0_lfp/probe_0_lfp_data/data
/acquisition/probe_1_muae/data
```

`FIXT` (the repository fixture, unextended):

| Candidate | Selects | Newly selected vs C0 | No longer selected vs C0 |
|---|---|---|---|
| C1 | the 3 corpus paths + `convolved` | `/processing/convolved_spike_train/convolved_spike_train_data/data` | — |
| C2 | the 3 corpus paths + `convolved` | `/processing/convolved_spike_train/convolved_spike_train_data/data` | — |
| C3 | the 3 corpus paths | — | — |
| C4 | nothing | — | all 3 |
| C5 | nothing | — | all 3 |
| C6 | nothing | — | all 3 |

`FIXT+typed`:

| Candidate | Newly selected vs C0 | No longer selected vs C0 |
|---|---|---|
| C1 | `/acquisition/eye_position/data`, `/acquisition/my_custom_series/data`, `/analysis/derived_metric/data`, `/processing/convolved_spike_train/convolved_spike_train_data/data` | — |
| C2 | the four above **plus `/acquisition/photodiode/data`** | — |
| C3 | `/acquisition/eye_position/data`, `/acquisition/photodiode/data`, `/acquisition/my_custom_series/data` | — |
| C4 | `/processing/convolved_spike_train/convolved_spike_train_data/data`, `/processing/spike_train/spike_train_data/data` | `/acquisition/probe_0_lfp/probe_0_lfp_data/data` |
| C5 | — | `/acquisition/probe_0_lfp/probe_0_lfp_data/data` |
| C6 | — | all 3 |

Per-dataset float64→float32 round-trip error on `FIXT+typed`, so "newly lost" is a quantity:

```
/acquisition/eye_position/data                                 err=9.000288e-07 bit_identical=False ndim=2
/acquisition/my_custom_series/data                             err=1.183501e-07 bit_identical=False ndim=2
/acquisition/photodiode/data                                   err=1.184242e-07 bit_identical=False ndim=1
/acquisition/probe_0_lfp/data                                  err=7.584658e-06 bit_identical=False ndim=2
/acquisition/probe_0_lfp/probe_0_lfp_data/data                 err=7.355104e-06 bit_identical=False ndim=2
/acquisition/probe_1_muae/data                                 err=7.613257e-06 bit_identical=False ndim=2
/analysis/derived_metric/data                                  err=1.190664e-07 bit_identical=False ndim=2
/processing/convolved_spike_train/convolved_spike_train_data/data  err=1.189489e-07 bit_identical=False ndim=2
```

No dataset on any fixture is bit-identical under the cast. C6 selects nothing for that reason.

## 5. A fourth consideration the item's (a), (b), (c) do not cover

**The selector is not the only thing that decides what is lost, and the override is silent and
mis-stamped.**

`convert()` runs the selector loop first, then unconditionally rewrites `SPIKE_TRAIN_PATH` and
`CONVOLVED_PATH` at the *source* dtype, re-reading from the source file. A candidate that
selects either path has its cast undone. Measured:

```
C1 float64 and 2-D
    spike_train selected=False int16->int16   bit_identical=True  stamp=False
    convolved   selected=True  float64->float64 bit_identical=True  stamp=True
C4 parent neurodata_type == ElectricalSeries
    spike_train selected=True  int16->int16   bit_identical=True  stamp=True
    convolved   selected=True  float64->float64 bit_identical=True  stamp=True
```

The data is preserved. The **provenance is not**: `_replace_dataset_data` re-applies the old
attributes, so the `stored_dtype_note` the selector loop wrote survives onto the restored
dataset. The output file carries

```
cast from float64 to float32 at write time by jnwb.compress_fp32 v0.2.5 on 2026-09-20;
measured max abs round-trip err 1.189489e-07
```

on a dataset that is bit-identical float64. A reader is told an irreversible cast happened
where none did.

Why this bears on the ruling: option (b) makes selection an explicit caller input. A caller who
names `processing/convolved_spike_train/.../data` in `select=` today gets a no-op plus a false
receipt, so `select=` would not mean what its name says. Whatever is ruled about the default,
the override layer needs its own disposition. This is recorded, not repaired — the packet
changes no behaviour.

Incidental, same layer: `drop_convolved=True` combined with any candidate that selects the
convolved path raises `KeyError: "Unable to synchronously open object (object 'data' doesn't
exist)"`, because the drop deletes the dataset before the selector loop reaches it.

## 6. The item's three recorded facts, confirmed or refuted

| Recorded in 06-13 | Verdict | Receipt |
|---|---|---|
| The fixtures carry **zero** `neurodata_type` attributes, so candidate 4 selects nothing there | **Confirmed** | `FIXT neurodata_type attrs = 0`, `FIXT+ = 0`; C4 selects nothing on both |
| `convolved_spike_train` is float64 and deliberately not downcast, so dtype and rank cannot separate it from LFP | **Confirmed for the selector, refuted as an outcome** | `lfp dtype=float64 ndim=2`, `convolved dtype=float64 ndim=2`, `-> share dtype AND rank: True`. But end to end the constant restores it bit-identical, so C1 and C2 do **not** in fact downcast it — §5 |
| A standard NWB file (`ElectricalSeries` plus an `ecephys` module) is refused outright with `KeyError` | **Half true** | `STD-ES` (ElectricalSeries, `processing/` empty) → **SUCCEEDED (not refused)**. `STD-PROC` (ecephys present) → **REFUSED KeyError**. The refusal comes from the `SPIKE_TRAIN_PATH`/`CONVOLVED_PATH` guard firing on a non-empty `processing/`, not from selection and not from `ElectricalSeries` |

## 7. Receipts

Every probe prints its import provenance first and asserts it.

| Column or claim | Probe | Output |
|---|---|---|
| `neurodata_type` counts | `p_candidates.py` FACT A | `FIXT 0 / FIXT+ 0 / FIXT+typed 7` |
| dtype+rank cannot separate convolved from LFP | `p_candidates.py` FACT B | `-> LFP and convolved share dtype AND rank: True` |
| Exact selected sets, all candidates × 3 populations | `p_candidates.py` SELECTION | `work/selection.json` |
| Newly lost / newly preserved set differences | `p_candidates.py` DIFFERENCES | `work/selection.json` |
| Per-dataset loss quantity | `p_candidates.py` LOSS | §4 block above |
| 06-79 rank change | `p_endtoend.py` | `_chunk_shape((1000,), 16384) -> (1000,)`; `(100, 8, 4) -> (100, 8, 4)`; scalar raises `ValueError` |
| LFP / MUAe / spikes / behavioural / arbitrary columns | `p_endtoend.py` END TO END | per-dataset `src dtype -> dst dtype` after a real `compress_fp32` run |
| Standard NWB refusal | `p_endtoend.py` STANDARD NWB | `STD-ES: SUCCEEDED`; `STD-PROC: REFUSED KeyError` |
| 1-D behavioural cast, post-06-79 | `p_mechanism.py` M3 | `photodiode ndim=1 float64->float32 max_abs_err=1.184242e-07 chunks=(1000,)` |
| pynwb ElectricalSeries group contents | `p_mechanism.py` M2 | `members: ['data', 'electrodes', 'starting_time']` |
| Contract under each candidate | `p_contract.py` M4 | table in §8 |
| Constant overrides selection; false stamp | `p_stamp.py` M5 | §5 block above |

## 8. What each candidate costs the existing contract

`tests/test_compression.py`, 61 tests, with each candidate installed as
`jnwb.compression._find_lfp_muae_paths` for the run. No test file was modified.

| Candidate | Result | Representative failures |
|---|---|---|
| **C0** | **61 passed** | — |
| C1 | 17 failed, 44 passed | `test_the_selector_selects_exactly_the_corpus_set`, 8 × `test_a_path_outside_the_named_group_is_rejected`, `test_a_dataset_of_any_rank_compresses`, `test_an_adversarial_file_writes_its_non_corpus_arrays_through_untouched` |
| C2 | 11 failed, 50 passed | the 8 adversarial-path tests, `test_a_renamed_acquisition_group_is_not_reached_by_a_tail_match`, `test_the_selector_selects_exactly_the_corpus_set` |
| **C3** | **3 failed**, 58 passed — the least breakage of any candidate | `test_a_path_outside_the_named_group_is_rejected[acquisition/my_probe_0_lfp/data]`, `test_a_renamed_acquisition_group_is_not_reached_by_a_tail_match`, `test_the_selector_selects_exactly_the_corpus_set` |
| C4 | 15 failed, 46 passed | all 3 × `test_the_corpus_paths_are_still_selected`, `test_compress_fp32_synthetic_hdf5_conversion`, `test_the_2d_data_survives_the_roundtrip_unchanged_in_value` |
| C5 | 15 failed, 46 passed | same set as C4 |
| C6 | 21 failed, 40 passed | the C4 set plus the 8 adversarial-path tests |

C3's three failures are all about *reaching too far by name*, not about dropping LFP: it selects
`acquisition/my_probe_0_lfp/data`, the P-29 shape the anchoring exists to reject. Every C4/C5/C6
failure is the opposite — the corpus LFP stops being selected at all.

## 9. Unresolved

| Cell | Why | What would settle it |
|---|---|---|
| Every candidate's behaviour on the 22-session corpus | `D:` is out of scope for this packet | Re-run `p_candidates.py`'s predicates over `artifacts/data/corpus_manifest.json`, read-only, recording on-disk bytes per element |
| Whether real behavioural series lose value under C2/C3 | Same | The prior packet sampled ~2.7% and found the cast bit-exact there; that is bounded and predates 06-79 |
| C4/C5 on a real nested-layout session | Same, and the fixture cell is construction-dependent (§2) | Read `neurodata_type` on the inner vs outer group of a real nested session |
