# NWB structural authority — 0.1.8

**Generated:** 2026-09-11  
**Scope:** structure only. No condition semantics, subject IDs, cortical aliases, or biological claims.  
**Provenance:** read-only inspection of `C:\workspace\_stale_omission_clone_20260909` (code/docs/artifacts) and `D:\nwb\omission\` (22 on-disk NWBs via h5py metadata probes; no data arrays loaded).  
**Not inspected:** `D:\nwb\mglo\` (directory exists, **zero** `.nwb` files observed).

**Fidelity rule:**

$$\text{structural fidelity} \neq \text{scientific/task-semantic fidelity}$$

Synthetic fixtures (`test-synth-task`, `test-synth-rf`, `test-synth-flash`) must reproduce the NWB **layouts** jnwb must parse, not simulate omission/RF/flash experiments scientifically. Use neutral table names and `test-synth-1` / `test-synth-2` code labels in fixtures.

---

## A. jnwb-local baseline (pre-omission survey)

| Claim | Status | Receipt |
|---|---|---|
| MCP synthetic uses `acquisition/ElectricalSeries`, `/electrodes`, `/intervals/stim_events` with string `code` | **observed** | `tests/test_mcp_server.py` |
| Autodiscover: `trials` → sole table → else `AmbiguousPath` | **observed** | `jnwb/mcp_server/event_tools.py`, `tests/test_mcp_server.py` |
| Code-column fallback order ends at substring `code` | **observed** | `jnwb/mcp_server/event_tools.py` |
| Minimal units+electrodes NWB (no LFP) | **observed** | `tests/test_hdmf_nwb_read_boundary.py` |
| Historical `vflip2_mapping` in jnwb git | **observed** | PSD/laminar algorithm only — **not** an RF-mapping NWB layout (`artifacts/capability_review_0.1.7.md`, `git show ae906a4:codes/functions/vflip2_mapping.py`) |

---

## B. Corpus overview (omission-task sessions on disk)

| Claim | Status | Receipt |
|---|---|---|
| 22 session NWBs at `D:\nwb\omission\` | **observed** | `artifacts/data/nwb_catalog.json`; live `glob('*.nwb')` count |
| Filename patterns: `sub-*_ses-*_rec.nwb` (most) or `sub-V182o_ses-*.nwb` (no `_rec`) | **observed** | `nwb_catalog.json`; h5py probes |
| All 22 share `intervals/omission_glo_passive` | **observed** | h5py probe all 22 |
| 21/22 also have `intervals/flash` | **observed** | h5py probe all 22 |
| 20/22 also have `intervals/rf_mapping_v2` | **observed** | h5py probe all 22 |
| 1/22 has omission-only interval set (no flash, no rf) | **observed** | `sub-V198o_ses-230629_rec.nwb` |
| Auxiliary interval tables on most files: `photodiode_1_detected_changes`, `reward_1_detected` (`id`, `start_time`, `stop_time` only) | **observed** | h5py probes |

**Loader code (omission repo, structure citations only):**

- Default task interval name: `omission_glo_passive` — `jnwb_ext/session.py:81-88`
- h5py required task columns: `start_time`, `trial_num`, `stimulus_number`, `task_condition_number` — `jnwb_ext/analog.py:193-196`
- h5py acquisition pattern: `acquisition/probe_{N}_lfp` / `_muae`, 2-D `(time, channel)` — `jnwb_ext/analog.py:269-317`
- Electrodes: `general/extracellular_ephys/electrodes` with `id`, `location`, `group_name` or `probe` — `jnwb_ext/analog.py:127-140`
- Units: top-level `units` with `spike_times` (+ index), `peak_channel_id`, QC columns — h5py + `jnwb_ext/session.py:360-367`
- PyNWB vs h5py: some sessions need h5py because Device metadata breaks full PyNWB read — `jnwb_ext/analog.py:1-6`
- LFP may be direct `ElectricalSeries` or `LFP` container with nested `*_data` child — `jnwb_ext/report.py:444-448`; confirmed on disk (see §E)

---

## C. Structural class 1 — task / omission-like (`test-synth-task`)

**Source table (provenance):** `/intervals/omission_glo_passive`  
**Synthetic fixture target:** `test-synth-task.nwb` with a **neutral** primary interval table (e.g. `test_synth_task`) mirroring this column set.

### C.1 Top-level groups (shared across classes)

**observed** on representative files: `acquisition`, `analysis`, `general`, `intervals`, `processing`, `stimulus`, `units`, plus scalar datasets `identifier`, `session_description`, `session_start_time`, `timestamps_reference_time`.

### C.2 Interval table — task

| Field | Status | Detail |
|---|---|---|
| Path | **observed** | `/intervals/omission_glo_passive` |
| Row count | **observed** | session-dependent (e.g. 4,163–15,586 rows) |
| `start_time` | **observed** | `float64`, seconds |
| `stop_time` | **observed** | `float64`, seconds; often equals `start_time` (point-like events) |
| `codes` | **observed** | primary event-code column (not `code`); dtype **`object`** (12/22 files) or **`float64`** (10/22, all V182o) |
| `task_condition_number` | **observed** | `object` or `float64`; string forms like `'1.0'` in object cohort |
| `stimulus_number` | **observed** | `object` or `float64`; phase index when present |
| `trial_num` | **observed** | `object` or `float64`; **not unique** within session |
| `correct` | **observed** | present on all probed files; defaults to 1.0 if absent per loader |
| `is_omission` | **observed** | present on 12/22 files (C31o/V198o cohort); **absent** on all 10 V182o files |
| Optional stimulus metadata columns | **observed** | e.g. `contrast`, `orientation`, `size`, `x_position`, `y_position`, `gabor`, `spatial_frequency`, `task_block_number`, `task_sequence`, screen/fixation fields — many nullable per row |

**Sample code values (provenance only, not for fixtures):** `9.0`, `50.0`, `40.0`, `100.0`, `101.0`.

### C.3 Acquisition (task sessions)

| Object pattern | Status | Detail |
|---|---|---|
| `acquisition/probe_{0..3}_lfp` | **observed** | 1–4 probes depending on session |
| `acquisition/probe_{N}_muae` | **observed** | parallel to LFP |
| Data layout | **observed** | `(n_samples, n_channels)` float32 |
| `starting_time` | **observed** | scalar dataset, typically `0.0` |
| Sampling rate | **observed** (indirect) | 1000 Hz from `artifacts/precompute_v182o.log` and `jnwb_ext/analog.py` rate resolution; **not** stored as a top-level `rate` dataset in h5py probes |
| `electrodes` reference child | **observed** | under each probe series |
| Behavioral series | **observed** | `pupil_1_tracking`, `eye_1_tracking`, `photodiode_1_tracking`, `reward_1_tracking` |

**Representative shapes (observed):**

- C31o `sub-C31o_ses-230816_rec.nwb`: `probe_0_lfp` → `(18071954, 128)` float32, 4 probes
- V198o `sub-V198o_ses-230629_rec.nwb`: 2 probes, `(2997445, 128)` each

### C.4 Electrodes

| Column | Status | Dtype (observed) |
|---|---|---|
| `id` | **observed** | int32 |
| `location` | **observed** | object |
| `group_name`, `probe` | **observed** | object (both may exist) |
| `x`, `y`, `z`, `imp`, `filtering`, `label`, `group` | **observed** | per `sub-V198o_ses-230629_rec.nwb` h5py probe |

### C.5 Units

| Column | Status | Notes |
|---|---|---|
| `spike_times` | **observed** | flat float64 array + `spike_times_index` per unit |
| `peak_channel_id` | **observed** | indexes global electrodes table |
| `cluster_id` | **observed** | per-probe local id (not global unit key) |
| QC metrics | **observed** | `quality`, `snr`, `firing_rate`, `isi_violations`, waveform fields, etc. |

---

## D. Structural class 2 — RF-mapping-like (`test-synth-rf`)

**Source table (provenance):** `/intervals/rf_mapping_v2`  
**Synthetic fixture target:** `test-synth-rf.nwb` with neutral interval table (e.g. `test_synth_rf`) mirroring this schema.

| Field | Status | Detail |
|---|---|---|
| Presence | **observed** | 20/22 omission corpus files |
| Row count | **observed** | session-dependent (e.g. 1,353–2,682) |
| `start_time`, `stop_time` | **observed** | `float64`, seconds |
| `codes` | **observed** | primary code column; object or float64 by cohort |
| `x_position`, `y_position` | **observed** | mapping coordinates; often NaN on non-stimulus rows |
| `x_position_negative`, `y_position_negative` | **observed** | RF-specific mirror columns |
| `contrast`, `size`, `spatial_frequency`, `phase`, `gabor`, `shape` | **observed** | stimulus parameter columns |
| `trial_num`, `correct`, `task_sequence` | **observed** | trial bookkeeping |
| `task_condition_number` | **observed absent** | not a column in `rf_mapping_v2` (unlike task/flash) |
| `stimulus_number` | **observed** | present; often NaN except stimulus rows |

**Distinction from task:** RF table carries spatial/stimulus-parameter columns and lacks `task_condition_number`; task table carries `task_condition_number` and (sometimes) `is_omission`.

---

## E. Structural class 3 — flash-like (`test-synth-flash`)

**Source table (provenance):** `/intervals/flash`  
**Synthetic fixture target:** `test-synth-flash.nwb` with neutral interval table (e.g. `test_synth_flash`).

| Field | Status | Detail |
|---|---|---|
| Presence | **observed** | 21/22 omission corpus files |
| Row count | **observed** | ~300–330 per probed session |
| `start_time`, `stop_time` | **observed** | `float64`; can differ (non-zero event duration) |
| `codes` | **observed** | e.g. `9.0`, `100.0`, `101.0` in provenance |
| `stimulus_number` | **observed** | phase-like index on stimulus rows |
| `task_condition_number` | **observed** | present |
| `trial_num`, `correct`, `task_block_number` | **observed** | trial bookkeeping |
| RF spatial columns (`x_position`, `contrast`, `gabor`, …) | **observed absent** | slimmer schema than RF/task |

**Distinction from RF:** flash table includes `task_condition_number` and omits RF spatial-parameter columns (`x_position_negative`, `gabor`, `spatial_frequency`, etc.).

---

## F. Cross-class distinctions a generic reader must handle

| Dimension | Task (`omission_glo_passive`) | RF (`rf_mapping_v2`) | Flash (`flash`) |
|---|---|---|---|
| Primary code column | `codes` | `codes` | `codes` |
| Condition column | `task_condition_number` | **none** | `task_condition_number` |
| Spatial params | optional/nullable | **core columns** | absent |
| `is_omission` | sometimes present | absent | absent |
| Multiple tables per file | **yes** | **yes** | **yes** |
| Explicit table selection | **required** when >1 candidate and no `trials` | same | same |
| Code dtype | string-object or float64 | same | same |
| Onset column | `start_time` (seconds) | same | same |
| Time base | session seconds from `starting_time` + uniform rate on acquisitions | same | same |

### F.1 Acquisition packaging (orthogonal to interval class)

| Style | Status | Detail |
|---|---|---|
| **Direct** `ElectricalSeries` | **observed** | 12/22 files; `acquisition/probe_N_lfp/{data,electrodes,starting_time}` |
| **Wrapped** `LFP` container | **observed** | 10/22 files (V182o); `acquisition/probe_N_lfp/probe_N_lfp_data/{data,electrodes,starting_time}` |
| Behavioral wrappers | **observed** | V182o uses typed containers (`PupilTracking`, `EyeTracking`, `BehavioralTimeSeries`) vs flat `TimeSeries` |

`jnwb.inspect` and signal readers must surface both shapes.

---

## G. Unknown / insufficient evidence

| Item | Status |
|---|---|
| `D:\nwb\mglo\` NWB layout | **unknown** — directory empty (no `.nwb` files) |
| RF/flash in omission **code** loaders | **unknown** — no `jnwb_ext` loader targets `rf_mapping_v2` or `flash` by name (grep); structure established from **on-disk NWBs only** |
| Complete per-column dtype matrix for all 22 sessions | **unknown** — three representative files probed in detail; corpus counters for interval sets and dtypes |
| Explicit `rate` dataset location | **unknown** on disk — rate inferred by omission loaders from attrs / sample spacing |
| Whether flash/RF tables exist outside omission corpus | **unknown** — not in jnwb; mglo empty |

---

## H. Fixture review (§0 acceptance)

| Fixture | Blocker before survey | After survey | Minimum synthetic structure |
|---|---|---|---|
| `test-synth-task` | partial (MCP-only) | **unblocked** | LFP acquisition + electrodes + units + task-like interval (`start_time`, `codes`, `task_condition_number`, `stimulus_number`, `trial_num`, `correct`) |
| `test-synth-rf` | blocked | **unblocked** | RF-like interval (`codes`, `start_time`, `x_position`, `y_position`, `contrast`, `size`, …) + shared acquisition/electrodes/units (minimal) |
| `test-synth-flash` | blocked | **unblocked** | Flash-like interval (`codes`, `start_time`, `stimulus_number`, `task_condition_number`, `trial_num`) + shared acquisition/electrodes/units (minimal) |

**Design requirements for §2–§3 (not blockers):**

1. Public event API must use **explicit interval table names** — real files have 3–5 tables.
2. Primary code column in this corpus is **`codes`**, not `code`; fallback order in `event_tools.py` must remain documented.
3. Support **numeric and string-like** code values (`object` strings vs `float64`).
4. `jnwb.inspect` must report **acquisition neurodata_type** (`ElectricalSeries` vs `LFP` wrapper) and nested data paths.

**§1 may proceed** under normal Review → Progress loop.
