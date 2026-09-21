# `compress_fp32` candidate-policy table (06-69)

> **Partly superseded, 2026-09-20 (P-106).** Read this notice before citing any row.
>
> | Still holds | Superseded |
> |---|---|
> | The **real-corpus measurements** -- C-1, C-2, C-3, the per-session selection histograms and section 3. Selection logic did not change after this baseline, so which paths each candidate selects is unaffected. **C-1 is the finding that most bears on the ruling: every dataset today's rule selects is already float32 on all 22 sessions, so the cast is the identity there.** | **The row labelled "R1 today" is no longer today.** P-29 is `repaired`; the shipped selector is the anchored `fullmatch` form, which this table calls R2. Every "newly lost vs today" cell is therefore measured against a baseline row that has moved -- harmless on the corpus, where R1 and R2 are identical on all 22, but not on the adversarial-path column. |
> | The **options (a) and (b)** definitions, as rows R4 and R3. | **Every contract count.** 06-78 took `tests/test_compression.py` from 15 tests to 61, so "15 passed", "4 failed, 11 passed" and "1 failed, 14 passed" are all stale. |
> | The P-30 evidence that 22 of 22 real files carry the dead-script stamp. | **Section 4's 1-D crash.** 06-79 made `_chunk_shape` follow rank, so R8/R9 no longer abort on a 1-D float64 series -- they **silently downcast** it. A loud refusal became a silent irreversible cast, which inverts those rows' real-corpus verdicts. |
> | -- | **Section 5's P-29 and P-30**, both now `repaired`. |
>
> For the current fixture measurement of the generic candidates, and for the premise verdicts,
> use `artifacts/compress_fp32_default_candidates.md` (baseline `c0d53a47`). This file remains
> the only source for the 22-session corpus numbers.

Evidence for the 06-13 ruling. Assembled by measurement; no cell is read off the source.
**This table does not choose a default.** 06-13 is `AUTONOMY: none`.

- Baseline: `577847f2aa7203f2d06e03b870de56fbe89e1d81`, tree clean.
- Library measured: `C:\workspace\jnwb\jnwb\compression.py`, sha256[:16] `836033feca65ff71`.
  Every probe asserts `jnwb.compression.__file__` resolves into the working tree. The installed
  copy in `C:\Python314\Lib\site-packages\jnwb` is byte-identical for this module, so the
  distinction does not change any number here — but it was asserted, not assumed.
- Two measurement populations, reported separately because **they disagree**:
  - **FIXTURE** — the `tests/test_compression.py` fixture and a superset of it, built with h5py.
  - **REAL** — 22 readable sessions from `artifacts/data/corpus_manifest.json`, opened read-only,
    metadata and bounded slices only. Nothing was written to D: or E:.
- On-disk dtype is read from the HDF5 datatype message in **bytes per element**
  (`dset.id.get_type().get_size()`), cross-checked against `get_storage_size()/npoints`. numpy's
  `.dtype` is recorded for reference only and is never the evidence.

---

## 0. Three contradictions with 06-13's stated premises

06-13's candidate table was measured on the fixtures alone. On the real corpus it inverts.

### C-1. The real corpus is **already float32**. The cast is a no-op there.

06-13 frames every candidate as a float64 → float32 downcast of LFP/MUAe. Measured across all
22 sessions: today's rule selects **142 datasets, every one of them already 4 bytes/element**.

```
R1_today_unanchored_corpus_regex
   n-selected histogram : {4: 4, 6: 9, 8: 9}
   on-disk size of selected datasets (bytes/elem): {4: 142}
```

A bounded read-only slice confirms the cast is the identity there:

```
probing /acquisition/probe_0_lfp/data  on-disk 4B/elem shape=(18071954, 128)
  slice dtype float32; astype(float32) bit-identical = True; max abs err = 0.000000e+00
```

Every real file already carries `conversion_script_version = v2` and a `stored_dtype_note` on the
selected datasets. **Consequence for the ruling:** on the corpus as it exists today, the choice
between R1/R2/R4 loses nothing new, because there is nothing left to lose. What the default
governs is *future* files and *non-corpus* files, not the data already on disk.

### C-2. `neurodata_type` is **not vacuous on real data — it is inconsistent**, and where it fires it selects the series the docstring promises to preserve.

06-13: "The corpus fixtures carry **zero** `neurodata_type` attributes, so type-based selection
selects nothing there." The fixture half is reproduced and true. The inference that type-based
selection is therefore a non-starter does not survive the real corpus, and the real failure is
worse than vacuity:

```
convolved_spike_train container typed ElectricalSeries in 9 of 22 sessions
spike_train           container typed ElectricalSeries in 9 of 22 sessions
  session  0..6, 17..21 : convolved_spike_train -> TimeSeries
  session  7..11, 13..16: convolved_spike_train -> ElectricalSeries
  session 12            : convolved_spike_train -> <absent>
```

The same logical series is typed `ElectricalSeries` in 9 sessions, `TimeSeries` in 12, and
carries no attribute in 1. So `neurodata_type` selection over the corpus:

```
R5_neurodata_type_ElectricalSeries
   n-selected histogram : {4: 4, 6: 8, 8: 2, 10: 8}
   on-disk size of selected datasets (bytes/elem): {2: 9, 4: 151}
   NEWLY selected vs today: {'spike_train_data': 9, 'convolved_spike_train_data': 9}
   NO LONGER selected vs today: {}
```

It selects `convolved_spike_train` — deliberately preserved — on 9 sessions, and `spike_train`,
which is **int16 (2 bytes/element)**, on the same 9. Casting int16 binned spike counts to float32
is not a precision downcast; it is a type change in a different family. 06-13 records R5's defect
as "no longer casts `probe_0_lfp`". Measured on real data it never drops anything; its defect is
that it *adds* the two datasets the contract exists to protect.

### C-3. "A standard NWB file is refused outright with `KeyError`" is **half true**, and the half that is true has nothing to do with `ElectricalSeries`.

```
standard NWB, processing/ EMPTY
   processing/ modules = []
   compress_fp32 -> SUCCEEDED (not refused)
standard NWB + populated ecephys module
   processing/ modules = ['ecephys']
   compress_fp32 -> REFUSED KeyError: "processing/spike_train/spike_train_data/data not found
     in std_1.nwb, but processing/ is non-empty (contains ['ecephys']) -- ..."
```

Both files are pynwb-written and both contain an `ElectricalSeries` (67 objects carry
`neurodata_type`). The refusal is produced by the `SPIKE_TRAIN_PATH`/`CONVOLVED_PATH` guard at
`jnwb/compression.py:326`, which fires on a **non-empty `processing/`**, whatever is in it. A
standard NWB file with no processing module converts successfully today. This matters to the
ruling because 06-13 cites the refusal as evidence that the tool is corpus-bound at the
*selection* layer; the measurement puts it at the *spike-train constants* layer instead, which
option (b) does not touch.

---

## 1. The table — columns 1–6

`FIXT` = the h5py corpus fixture (no `neurodata_type`, no `unit`). `FIXT+attr` = same fixture
with `neurodata_type`/`unit` populated. `REAL` = the 22-session corpus.
"DOWNCAST 8B→4B" is measured on disk in bytes, with the max abs error from the same run.

| # | Exact selection rule (pasteable) | Current behaviour | LFP | MUAe | Other acquisition series (`eye_position` / tracking) | Processing-module series (`ecephys/proc_series`; `convolved_spike_train`) |
|---|---|---|---|---|---|---|
| **R1** today | `re.compile(r"(probe_\d+_(?:lfp\|muae))(?:/\1_data)?/data$").search(name)` | **Ships today.** FIXT: 2 selected. REAL: 4/6/8 per session, 142 total, all already 4B. Adversarial: **6 of 6** wrong-group paths selected (P-29). | FIXT **DOWNCAST 8B→4B**, max err 7.584658e-06. REAL selected, already 4B, cast is identity (err 0.0). | FIXT **DOWNCAST 8B→4B**, max err 7.613257e-06. REAL as LFP. | **preserved 8B**, max_abs_err 0.0 (FIXT and REAL — tracking series untouched). | **preserved 8B** both. `convolved_spike_train` bit-identical after conversion: `True`. |
| **R2** anchored preset | `re.compile(r"^acquisition/(probe_\d+_(?:lfp\|muae))(?:/\1_data)?/data$").fullmatch(name)` | FIXT: 2 selected, same as R1. REAL: identical to R1 on all 22 (142 datasets, all 4B). Adversarial: **0 of 6**. | Identical to R1 (**DOWNCAST 8B→4B**, 7.584658e-06). | Identical to R1 (**DOWNCAST 8B→4B**, 7.613257e-06). | **preserved 8B**. | **preserved 8B**; convolved bit-identical. |
| **R3** `select=` required | `if select is None: raise ValueError("select= is required; irreversible float32 downcast has no default"); paths = list(select)` | FIXT: **raises, no output file at all.** REAL: raised on **22 of 22**. With `select=` given: exactly the caller's list. | Silent caller: **no output**. `select=` given: **DOWNCAST 8B→4B**, 7.584658e-06. | Same. | **preserved** when not named; downcast only if the caller names it. | **preserved** unless named. |
| **R4** `select=`, preset default | `paths = list(select) if select is not None else ANCHORED_CORPUS_PRESET(f)` | FIXT: 2 selected (= R2). REAL: identical to R1/R2 on all 22. With `select=`: caller's list. | **DOWNCAST 8B→4B**, 7.584658e-06. | **DOWNCAST 8B→4B**, 7.613257e-06. | **preserved 8B**. | **preserved 8B**; convolved bit-identical. |
| **R5** `neurodata_type` | `basename(name)=="data" and obj.parent.attrs.get("neurodata_type")=="ElectricalSeries"` | FIXT: **selects nothing** (0 attrs). FIXT+attr: 3. REAL: 4/6/8/10 per session; **151 datasets at 4B + 9 at 2B**. | FIXT **preserved 8B** (rule vacuous). FIXT+attr **DOWNCAST 8B→4B**. REAL selected (already 4B). | Same as LFP. | **preserved 8B** everywhere (`eye_position` is `SpatialSeries`; tracking series untyped). | FIXT+attr: `proc_series` **DOWNCAST 8B→4B** (7.570564e-06). **REAL: selects `convolved_spike_train` on 9/22 and `spike_train` (int16, 2B) on 9/22.** |
| **R6** unit-driven | `basename(name)=="data" and obj.dtype==float64 and unit_of(obj) in ("volts","V","volt")` | FIXT: **selects nothing**. FIXT+attr: 4. REAL: **selects 0 on 22 of 22 sessions.** | FIXT/REAL **preserved 8B / not selected**. FIXT+attr **DOWNCAST 8B→4B**. | Same. | FIXT+attr: **`my_custom_series` DOWNCAST** (arbitrary user series carrying `unit=volts`). `eye_position` (`degrees`) preserved. | FIXT+attr: `proc_series` **DOWNCAST**. REAL: nothing selected. |
| **R7** float64 + 2-D | `obj.dtype==np.float64 and obj.ndim==2` | FIXT: 6 selected. REAL: 1–2 per session, 32 datasets, **all 8B — and none of them LFP/MUAe**. | FIXT **DOWNCAST 8B→4B**. **REAL: not selected at all** (real LFP is already float32). | Same as LFP. | FIXT `eye_position` **DOWNCAST** (7.067235e-06). REAL: `eye_1_tracking` **DOWNCAST**, 12 sessions. | FIXT `proc_series` **DOWNCAST**; `convolved_spike_train` **DOWNCAST in FIXT** (float64 2-D). REAL: convolved already 4B so not selected; **`/units/waveform_mean` selected on 10 sessions** — spike waveform templates, downcast as a side effect. |
| **R8** float64 + basename `data` | `obj.dtype==np.float64 and basename(name)=="data"` | FIXT: 6 selected. **Crashes on a 1-D float64 series** (see §4). REAL: exactly **3 per session, 66 total, all 8B, none of them LFP/MUAe**. | FIXT **DOWNCAST 8B→4B**. **REAL: not selected.** | Same. | FIXT `eye_position` **DOWNCAST**. REAL: `eye_1_tracking`, `photodiode_1_tracking`, `reward_1_tracking` **all DOWNCAST**, 12 sessions each. | FIXT `proc_series` and `convolved_spike_train` **DOWNCAST**. REAL: not selected (already 4B). |
| **R9** float64 + `acquisition/` + basename `data` | `obj.dtype==np.float64 and basename(name)=="data" and name.startswith("acquisition/")` | FIXT: 4 selected. **Same 1-D crash.** REAL: **3 per session, 66 total, all 8B, none of them LFP/MUAe.** | FIXT **DOWNCAST 8B→4B**. **REAL: not selected.** | Same. | FIXT `eye_position` **DOWNCAST**. REAL: the three tracking series **all DOWNCAST**. | **preserved 8B** (outside `acquisition/`). |

---

## 2. The table — columns 7–12

| # | Arbitrary user series (`my_custom_series`) | Data newly downcast (vs today) | Data no longer downcast (vs today) | Compatibility for a caller who already wrote files | Inferable from NWB semantics rather than names? | Reversible or irreversible | **Existing contract survives?** |
|---|---|---|---|---|---|---|---|
| **R1** | **preserved 8B** | — (it is today) | — | Baseline. `verify_roundtrip` ok; re-compress of an already-compressed file ok, LFP 4B→4B. **`tests/test_compression.py`: 15 passed.** | **No.** Name only. Renaming the series to a non-corpus name drops it to **0 selected** (`survives_rename=False`). | **IRREVERSIBLE.** Recovering float64 from the written file: `bit-identical False`, max abs diff 7.584658e-06, 1 distinct value collided. Nothing in the file records the pre-cast values. | **Yes** (definitional). |
| **R2** | **preserved 8B** | **None.** FIXT and all 22 REAL sessions select exactly what today selects. | **6 adversarial paths** under `stimulus/`, `analysis/`, `scratch/`, `general/…`, and `acquisition/my_probe_0_lfp` (P-29). On the real corpus: **nothing** — every real match already sits under `acquisition/`. | `verify_roundtrip` ok; re-compress ok (4B,4B). **15 passed.** | **No.** Name + location. `survives_rename=False`. | **IRREVERSIBLE** (same cast). | **Yes.** |
| **R3** | **preserved** unless named | **Nothing** — the caller names every cast. | **Everything, on every silent call.** REAL: raised on 22 of 22. | **Breaks.** `tests/test_compression.py`: **4 failed, 11 passed** — `test_compress_fp32_synthetic_hdf5_conversion`, `test_compress_fp32_unrecognized_processing_raises_key_error`, and both `TestVerifyRoundtripDoesNotDisableWarnings` tests. `verify_roundtrip(existing output)` itself **raises**, because it calls the same selector at `compression.py:447`. Re-compress raises. | **N/A** — nothing is inferred; the caller states it. `survives_rename=True` trivially. | The cast stays **IRREVERSIBLE**; this is the only candidate where it never happens without an explicit instruction. | **No.** 4 of 15 tests fail, and `verify_roundtrip` breaks for existing files. |
| **R4** | **preserved 8B** | **None** (FIXT and all 22 REAL). | **The same 6 adversarial paths as R2**; nothing on the real corpus. | `verify_roundtrip` ok; re-compress ok. **15 passed.** Signature gains a keyword-only `select=`; existing positional calls unchanged. | **No** when silent (name-based preset); **caller-stated** when `select=` is given. `survives_rename=True` with `select=`. | **IRREVERSIBLE** cast; the silent path stays implicit. | **Yes.** |
| **R5** | **preserved** (typed `TimeSeries`) | **FIXT+attr:** `proc_series`. **REAL: `convolved_spike_train` on 9/22 sessions and `spike_train` (int16→float32) on 9/22.** Selects the series the docstring preserves. | **FIXT: LFP and MUAe** — nothing is selected at all, because 0 objects carry the attribute. **REAL: nothing.** | `verify_roundtrip` ok; re-compress ok. **1 failed, 14 passed** — `test_compress_fp32_synthetic_hdf5_conversion`, which asserts `dst_lfp.dtype == np.float32`. | **Yes in form** (`survives_rename=True`), **but measured unreliable**: the same logical series is `ElectricalSeries` in 9 sessions, `TimeSeries` in 12, absent in 1. It reads the data model; the data model disagrees with itself. | **IRREVERSIBLE**, and on 9 sessions it would irreversibly convert **int16** spike counts to float32. | **No.** 1 of 15 tests fails; and it downcasts a series the docstring promises to keep. |
| **R6** | **FIXT+attr: DOWNCAST** — an arbitrary user series carrying `unit=volts` is selected. | FIXT+attr: `proc_series` and `my_custom_series`. **REAL: nothing.** | **FIXT: LFP and MUAe. REAL: LFP and MUAe on all 22 sessions** (`{'probe_1_lfp': 12, 'probe_0_lfp': 12, …}` — it selects 0 everywhere). | `verify_roundtrip` ok; re-compress ok. **1 failed, 14 passed** (same test). | **Yes in form** (`survives_rename=True`), **vacuous in fact**: 0 selected on 22 of 22 real sessions. `unit` is not populated where this rule reads it. | **IRREVERSIBLE** cast; in practice it performs none. | **No.** 1 of 15 tests fails, and it is a silent no-op on the entire real corpus. |
| **R7** | **DOWNCAST 8B→4B** (7.249213e-06) in FIXT. | FIXT: `eye_position`, `my_custom_series`, `proc_series`, **`convolved_spike_train`**. REAL: `eye_1_tracking` (12 sessions) and **`/units/waveform_mean` (10 sessions)**. | **REAL: all LFP and MUAe, on all 22 sessions.** FIXT: none. | `verify_roundtrip` ok; re-compress ok. **15 passed** — the suite does **not** protect `eye_position` or `convolved_spike_train`, because the test fixture contains neither in a form this rule reaches. Passing tests are not evidence of preservation here. | **No.** Storage properties (dtype, rank), not the data model. `survives_rename=True` only because it ignores names entirely. | **IRREVERSIBLE.** | **No.** Tests pass, but it downcasts `convolved_spike_train` in FIXT and on REAL selects `units` while dropping every LFP/MUAe. |
| **R8** | **DOWNCAST 8B→4B** in FIXT. | FIXT: `eye_position`, `my_custom_series`, `proc_series`, **`convolved_spike_train`**. REAL: `eye_1_tracking`, `photodiode_1_tracking`, `reward_1_tracking`, 12 sessions each. | **REAL: all LFP and MUAe, all 22 sessions.** | `verify_roundtrip` ok; re-compress ok. **15 passed** (same blind spot). **Crashes** on any 1-D float64 series: `ValueError: 'chunks' must have same rank as dataset shape` at `jnwb/compression.py:172`. The real corpus has two 1-D float64 series per session, so **this rule would abort on every real file**. | **No.** Storage properties only. | **IRREVERSIBLE.** | **No.** Downcasts `convolved_spike_train`, drops all LFP/MUAe on real data, and aborts on real files. |
| **R9** | **DOWNCAST 8B→4B** in FIXT. | FIXT: `eye_position`, `my_custom_series`. REAL: the three tracking series, 12 sessions each. | **REAL: all LFP and MUAe, all 22 sessions.** | `verify_roundtrip` ok; re-compress ok. **15 passed** (same blind spot). **Same 1-D crash**, and the 1-D series are under `acquisition/`, so it aborts on every real file too. | **No.** Storage properties + a path prefix. | **IRREVERSIBLE.** | **No.** Same as R8 minus the processing-module casts. |

---

## 3. What the tracking series would actually lose

Because R8/R9 are the candidates that would cast the behavioural channels on real data, their
loss was measured rather than assumed — 10 blocks of 50 000 rows spread across the full array,
in 4 sessions (≈500 000 of ≈18–20 million rows per series, ~2.7%):

```
eye_1_tracking         bit-identical in every sample = True; worst err 0.000000e+00; ndim=2
photodiode_1_tracking  bit-identical in every sample = True; worst err 0.000000e+00; ndim=1
reward_1_tracking      bit-identical in every sample = True; worst err 0.000000e+00; ndim=1
```

In the sampled region these float64 series hold values exactly representable in float32, so the
cast would lose no *value* there. It would still be an irreversible on-disk type change, and the
sample covers ~2.7% of each array — this is a bounded measurement, not a guarantee over the full
arrays. It does not rescue R8/R9, which abort on these same series (§4) before writing anything.

## 4. A mechanical defect any 1-D selection exposes

`convert()` builds a 2-D chunk shape unconditionally (`chunks = (min(16384, shape[0]), n_ch)`),
so selecting any 1-D dataset fails:

```
R7_float64_and_2d                     OK (no crash)
R8_float64_and_basename_data          ValueError: 'chunks' must have same rank as dataset shape
    raised at: File "C:\workspace\jnwb\jnwb\compression.py", line 172, in _replace_dataset_data
R9_float64_acquisition_basename_data  ValueError: 'chunks' must have same rank as dataset shape
    raised at: File "C:\workspace\jnwb\jnwb\compression.py", line 172, in _replace_dataset_data
```

Today's rule never selects a 1-D dataset, so the defect is latent. It is not a property of any
candidate — it is a property of the mechanics, and it blocks **R8, R9, and any `select=` call
naming a 1-D dataset**, which includes R3 and R4. Not repaired here; recorded for the
implementation item.

## 5. Notes on P-29 and P-30 (claimed by 06-65 / 06-66 — not repaired here)

- **P-29 reproduced.** Today's unanchored `.search()` selects **6 of 6** adversarial paths;
  the anchored form selects **0 of 6**. New measurement: on the real corpus the two are
  **identical on all 22 sessions**, so anchoring changes nothing on data that exists today. The
  exposure is to future or hand-built files, not to the corpus.
- **P-30 reproduced, and it is worse in production than in the fixtures.** All 22 real sessions
  stamp `conversion_script = "scripts/convert_nwb_compressed.py"`; that path is absent from the
  repository in **22 of 22**. `scripts/` exists and holds 12 other entries. Newly written files
  reproduce the same stamp, so the defect is still being minted.
- Incidental: `test_compression.py` passes under R7/R8/R9 while those rules downcast
  `convolved_spike_train`. The suite has no assertion that the preserved series stays float64.
  Whatever 06-13 rules, that gap is worth its own item.

## 6. Evidence index

All probes in `…/scratchpad/compress_policy/`; raw JSON under `work/`.

| Probe | Establishes |
|---|---|
| `p00_provenance.py` | which jnwb a by-path script imports (site-packages) vs the tree |
| `p01_facts.py` | the three carried facts; on-disk dtypes in bytes; P-29 |
| `p02_matrix.py` | end-to-end `compress_fp32` per candidate; rename/semantics test; 1-D behaviour |
| `p03_compat.py` | reversibility; `verify_roundtrip` and re-compress per candidate; standard NWB; P-30 |
| `p04_real.py` | per-candidate selection on real sessions; the standard-NWB refusal claim |
| `p05_contract.py` | `tests/test_compression.py` under each swapped selector; R1 vs R5 over 22 sessions |
| `p06_divergence.py` | exactly which paths R5 adds; wide sample of the tracking series |
| `p07_confirm.py` | `neurodata_type` per session on the spike-train containers; P-30 over 22 files |
| `p08_sweep.py` | all 9 candidates × 22 real sessions |

**Unmeasurable cells: none.** Every cell above is a measured outcome. Two are bounded rather than
exhaustive and are labelled as such: the tracking-series loss in §3 (~2.7% of each array) and the
real-corpus reads, which are metadata plus bounded slices because the files are 50–60 GiB each
and the corpus is read-only.
