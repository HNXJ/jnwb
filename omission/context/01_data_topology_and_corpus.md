# 01 — Data Topology and Corpus

Generated 2026-08-17 by repo-wide documentation audit. Every count below names its source file
and as-of date. **Do not quote a count from this document without re-checking its source** — per
CLAUDE.md, `scripts/discover_corpus.py --check` → `artifacts/data/corpus_manifest.json` is the
only path/count that overrides everything else, including this file.

## Current corpus (authoritative as of 2026-08-14)

Source: `artifacts/data/corpus_manifest.json` (`schema_version: 2`, `generated_utc:
2026-08-14T16:36:32Z`), cross-checked against `artifacts/data/session_readiness.csv`.

| Quantity | Value |
|---|---|
| Sessions | **22** |
| Subjects | **3** — `C31o`, `V182o`, `V198o` |
| NWB files ok | 22 / 22 |
| Sidecars ok | 0 / 22 (metadata_dir unresolved when this manifest was generated — `OMISSION_META_DIR` not set; WARNING, not blocking) |
| TFR ok | 22 / 22 sessions have ≥1 TFR product |
| TFR files on disk | **970**, all `.npz` |
| `suite_tfr_ready` (session_readiness.csv) | **0 / 22** — see "Open readiness-gate question" below |

Per-subject session breakdown:

| Subject | Alias (Hamm, 2026-08-16/17) | Sessions | Session IDs | TFR files/session |
|---|---|---|---|---|
| C31o | **Cajal** | 7 | 230816, 230818, 230823, 230825, 230830, 230831, 230901 | 50,50,60,50,50,50,50 |
| V182o | **Ivan** | 10 | 260629,260702,260706,260708,260710,260713,260715,260717,260722,260724 | 50,40,40,40,40,40,40,40,40,30 |
| V198o | **Joule** | 5 | 230629,230714,230719,230720,230721 | 40,40,50,40,40 |

**Subject aliases** (`ANIMAL_ALIAS`, defined identically in `scripts/classify_units_omission_inclusion_v1.py:64`
and `scripts/detect_lfp_bad_channels_trials.py:61`): `V182o=Ivan, C31o=Cajal, V198o=Joule`. All
three in scope for every current analysis track. Provenance: `context/analysis_spec_SPK.md`'s
original spec said "2 monkeys (Ivan + 1)" and "Ivan" did not appear anywhere in the repo at the
time — the mapping was obtained directly from Hamm (2026-08-16/17,
`artifacts/.lab/S1-unit-inclusion-rework-in-progress-20260817.json:12`).

## Root paths — always resolve via `jnwb.paths`, never hardcode

`jnwb/paths.py` (added 2026-08-08 after a drive-letter remap — `D:\workspace\omission` →
`C:\workspace\omission` — silently broke ~30 independently-hardcoded path literals across
`session.py`, `viz.py`, `report.py`, and ~27 scripts).

Two root classes:
- **Repo-internal** (`REPO_ROOT`, `outputs_dir()`, `artifacts_dir()`): derived from `__file__`,
  never configurable, always correct.
- **External data** (`nwb_dir()`, `analysis_dir()`, `tfr_dir()`, `meta_dir()`, `conndb_dir()`):
  live on a separate volume, env-var override, documented default fallback.

| Root | Env var | Default | Holds |
|---|---|---|---|
| `nwb_dir()` | `OMISSION_NWB_DIR` | `D:/nwb/omission` | `sub-*_ses-*_rec.nwb` session files. **`D:/nwb/mglo/` is a different experiment living alongside it — never glob the parent.** |
| `analysis_dir()` | `OMISSION_ANALYSIS_DIR` | `D:/analysis` | root of every derived artifact |
| `tfr_dir()` | `OMISSION_TFR_DIR` | `<analysis_dir>/tfr_arrays` | TFR products |
| `meta_dir()` | `OMISSION_META_DIR` | `<analysis_dir>/metadata` | per-session sidecars |
| `conndb_dir()` | `OMISSION_CONNDB_DIR` | `<analysis_dir>/connectivity_databases` | vFLIP2 `*_channel_layers.csv` |

Run `python -c "import jnwb.paths as p; print(p.describe())"` first after any drive remap —
lists every resolvable root with `{"path","exists"}`.

`resolve_nwb_path(prefix)` tries `{prefix}_rec.nwb` then `{prefix}.nwb`. `require(path, what,
env_var)` raises `FileNotFoundError` with a fix-it hint. `sha256_file()` is the canonical
chunked-digest helper (promoted 2026-08-14 from ten duplicated copies).

## `scripts/discover_corpus.py` — the source of truth

Docstring: "This script replaces every remembered path and count in project doctrine. It resolves
state; it does not encode it." No absolute path, subject name, session count, or file count is
hardcoded in it.

- `--check` exit codes: `0` resolved+passing, `1` resolved but blocking mismatch, `2`
  discovery/config failure.
- Scans NWB dir (`_scan_nwb`), TFR dir (`_scan_tfr`, matches products to sessions by
  **longest-matching `session_prefix` prefix**, not raw stem — fixed 2026-08-14, see below),
  sidecars (`_scan_sidecars`), then cross-checks against `session_readiness.csv`
  (`_crosscheck_readiness`) and `nwb_catalog.json` (`_crosscheck_catalog`).
- Writes `artifacts/data/corpus_manifest.json`.

**Fixed bug (2026-08-14):** `_scan_tfr` previously matched TFR filenames against the raw NWB
`stem` (which keeps a trailing `_rec` for most C31o/V198o files) instead of `session_prefix`
(never carries `_rec`). This silently undercounted `tfr_ok` to 10/22 instead of 22/22, and is the
exact mechanism behind the 2026-08-12 incident where the readiness table claimed **zero**
TFR-ready sessions while hundreds of TFR arrays sat on disk (`readiness_gate_unsatisfiable`,
BLOCKING-severity cross-check in `_crosscheck_readiness`).

## `session_readiness.csv` — 22 rows, one open gate

Columns: `stem, session_prefix, subject, session_id, short_nwb, nwb_ok, nwb_bytes, nwb_path,
sidecar_ok, tfr_ok, tfr_n_files, tfr_r_family_ok, tfr_conditions, suite_tfr_ready`.

- `nwb_ok=True`, `tfr_ok=True`, `tfr_r_family_ok=True` for all 22 rows.
- `sidecar_ok=False` for all 22 rows (metadata_dir unresolved at generation time).
- `tfr_conditions` identical across all 22 rows: `AAAX|AAXB|AXAB|BBBX|BBXA|BXBA|RRRR|RRRX|RRXR|RXRR`
  (the 10 omission-family condition tokens; AAAB/BBBA, the non-omission structured-standard
  conditions, are not part of this column).
- **`suite_tfr_ready=False` for all 22 rows — 0/22 sessions pass this specific gate.** Whether
  this is a real unmet requirement (e.g. missing AAAB/BBBA TFR products) or a stale/never-updated
  column was **not resolved by this audit** — read `scripts/build_session_readiness.py` before
  trusting or acting on this column. Flagged in [09_conflicts_and_flagged_discrepancies.md](09_conflicts_and_flagged_discrepancies.md).

## Known live discrepancy: `.npy` vs `.npz`

`corpus_manifest.json`'s disk scan finds **970 `.npz`** files, zero `.npy`. But
`omission/jnwb_ext/session.py::OmissionSession.tfr_from_preprocessed()` (lines 622-722) globs
`tfr_root.glob(f"{session_prefix}-*-{token}-{condition}.npy")` — **`.npy` only**. If the TFR
directory genuinely contains only `.npz` today, this loader returns `None` for every call
(`plot_tfr` degrades gracefully to `status="missing_tfr"`, per its own "no silent science"
comment — it will not fabricate a plot, but every call silently finds nothing). Not fixed by this
audit; flagged as a HIGH-risk conflict in doc09 — resolving it needs to know whether `.npz` is a
recent change (TFR products regenerated in a new format) or `.npy` was always wrong in the code.

## Condition maps — subject-specific

`omission/jnwb_ext/session.py:40-54`:

```python
CONDITION_MAP_DEFAULT = {
    'AAAB': [1, 2], 'AXAB': [3], 'AAXB': [4], 'AAAX': [5],
    'BBBA': [6, 7], 'BXBA': [8], 'BBXA': [9], 'BBBX': [10],
    'RRRR': list(range(11, 27)), 'RXRR': list(range(27, 35)),
    'RRXR': [35, 37, 39, 41], 'RRRX': [36, 38, 40] + list(range(42, 51)),
}
CONDITION_MAP_V182O = dict(CONDITION_MAP_DEFAULT, **{
    'RRXR': list(range(35, 43)), 'RRRX': list(range(43, 51)),
})
```

`condition_map_for_stem(stem)` dispatches on `"V182o" in stem`. Confirmed for C31o/V198o
(2026-07-30): conditions 35/37/39/41 omit `stimulus_number=4` (p3, odd slots only); 36/38/40/42-50
omit `stimulus_number=5` (p4) — an interleaved/odd-even split. V182o has no `is_omission` column
to re-derive this from directly; Hamm supplied the authoritative **contiguous** split (RRXR=35-42,
RRRX=43-50) from task-generation source markdowns
(`artifacts/.lab/condition_number_crosswalk_v182o_investigation_20260730.json`).

`stimulus_number` crosswalk: fx=1, p1=2, p2=3, p3=4, p4=5.

## Per-probe / per-area layout

`scripts/export_putative_layers.py` (vFLIP2 laminar assignment pipeline):

- **Channel layer**: spectrolaminar alpha/beta-to-gamma-power crossover from each probe's raw LFP
  Welch PSD → superficial/middle/deep per channel. Non-converging segments → `'na'`.
- **Unit layer**: a unit's putative layer = its peak channel's layer (Hamm, 2026-07-28). Join key
  `(session, probe, local_channel_index)` — **probe-local, not global electrode id.**
- **Coverage caveat**: only 53.9% of channels carry a real label overall; differs significantly by
  animal (Kruskal-Wallis H=12.80, P=0.0017) and ~3× by area. **Laminar contrasts are only
  interpretable within-animal and within-area** — never a pooled laminar coefficient (CLAUDE.md
  tripwire #8: check whether a column is constant/degenerate before interpreting it).

`PROBE_LETTER = {"probe_0_lfp":"A","probe_1_lfp":"B","probe_2_lfp":"C","probe_3_lfp":"D"}`.
`POOL = {"V3":"V3a/d","V3a":"V3a/d","V3d":"V3a/d"}` — matches the 10-area analysis scheme below.

Outputs: `outputs/layers/per_probe/<session>_<probe>.csv`, `channel_layers_all.csv`,
`unit_layers.csv` (every unit + peak-channel layer), `layer_coverage_summary.csv`, `receipt.json`.

**`outputs/layers/unit_layers.csv`** (2026-07-28 vintage, 9,228 rows — see staleness note below)
columns: `unit_id, peak_channel_id, area, quality, firing_rate, snr, presence_ratio,
session_prefix, unit_index, probe_id, local_channel, waveform_duration, PT_ratio, amplitude,
isolation_distance, silhouette_score, d_prime, isi_violations, display_class, is_s_plus,
is_s_minus, is_o_plus, probe, unit_layer, crossover_channel, channel_area10,
unit_layer_labelled, area10, animal`.

## Ten analysis areas

Canonical pooled-area scheme (`V3` subdivisions pooled to `V3a/d`): **V1, V2, V3a/d, V4, MT, MST,
TEO, FST, FEF, PFC.**

Every area is recorded in **at least 2** animals; V4 in all 3 — the area×animal design graph is
connected, so additive area+animal effects are jointly identifiable even though area and subject
are otherwise confounded corpus-wide (`omission-statistics` skill). Per-area animal coverage
(2026-07-28 inventory, session counts per animal):

| Area | Sessions by animal |
|---|---|
| V1 | C31o 4, V198o 5 |
| V2 | C31o 1, V198o 5 |
| V3a/d | C31o 5, V198o 5 |
| V4 | C31o 6, V182o 2, V198o 1 |
| MT | C31o 8, V182o 6 |
| MST | C31o 5, V182o 1 |
| TEO | C31o 3, V182o 9 |
| FST | C31o 1, V182o 1 |
| FEF | C31o 2, V182o 10 |
| PFC | C31o 6, V182o 8 |

**Segment-boundary caveat**: of 28 multi-area probes, 26 split at channel 64 of 128; one
three-area probe splits at 42 and 85. These are equal-share assumptions, not measurements. One
probe (`sub-V182o_ses-260724` probe C) declares 32 channels but its area slices span 128 and its
array holds 128 channels — channel-to-area mapping is **undeterminable**, excluded from
area-resolved analysis.

**Dual-area probes resolve by channel position** (channels 1-64 = one area, 65-128 = the other;
never `.split(',')[0]` on a combined location string — this mislabeled 1,965/6,655 rows once). Use
`jnwb.addressing.map_peak_channel_to_area`.

## `OmissionSession` (`omission/jnwb_ext/session.py`) — the per-session object

Disk-cache-first NWB loader: `artifacts/developer/.cache/<session>_{units,electrodes,intervals}.pkl`
+ `<session>_metadata.json`. `_REPO_ROOT` is imported from `jnwb.paths` specifically so the cache
path is CWD-independent (a 2026-08-04 incident duplicated a 6.7 GB, 21-session cache under a
figure subdirectory because a script happened to run from inside `context/figures/fig03_unit_census/`).

Key methods: `get_units(quality=None, area=None, firing_rate_range=None)`,
`get_electrodes(area=None)`, `get_epochs(phase=None, condition=None, correct_only=True)`,
`get_trial_onsets`, `get_spike_times(unit_id)`, `channel_unit_mapping()`, `lfp_channel_areas()`,
`tfr_from_preprocessed(area, band, condition, tfr_dir=None)`, `plot_tfr`, `raster_suite`,
`pie_charts`, `info`/`summary`.

**Identity footgun (documented in-code, `get_spike_times`, lines 326-338)**: primary lookup is by
**raw DataFrame row position**, not any `unit_id`/`cluster_id` column value — this is the actual
convention used corpus-wide (`unit_classification.classify_session_units`'s default `unit_ids =
list(units_df.index)`, and several scripts). The DataFrame `cluster_id`/`unit_id` **column** is a
per-probe-local kilosort id that resets to 0 per probe and is **not globally unique** (confirmed
2026-07-12 to collide across ≥3 areas within one session). Never treat that column as a stable
identity key across probes.

**`get_units(quality=...)` gap**: the docstring mentions `'mua'`/`'unstable'` tiers, but the method
body only implements `'stable_plus'` and `'stable'` branches — other quality strings silently pass
through with **no filter applied** (a real doc/code gap, not a bug in output, but a silent no-op
trap).

**CRITICAL PARADIGM TIMING INVARIANT** (`get_epochs` docstring): `stimulus_number` (phase) 2 = P1
onset (t=0 ms); phase 1 = fixation (t=−566 ms); phase 3 = P2 (t=1031 ms); phase 4 = P3 (t=2062 ms);
phase 5 = P4 (t=3093 ms).

**TFR array contract** (`tfr_from_preprocessed`): filename `{session_prefix}-{A|B|C|D}-{area}-{CONDITION}.npy`
(see `.npy`/`.npz` discrepancy above); float32 array `(n_trials, n_channels, n_freqs, n_times)`,
`freqs ≈ arange(3,201,2)` (99 freqs), `times ≈ -1000 + arange(500)*10` ms (500 bins @ 10 ms). Area
aliasing: V3d/V3a also try file token `V3`; V4 also tries `DP`; bare `V3` tries both `V3d`/`V3a`.

`baseline` in `trial_averaged_plot`/`plot_tfr` is the **first 20 bins (200 ms)** — must not be
`shape[1]//4`, which on the canonical 1000ms-pre/4000ms-post window reaches 250ms past stimulus
onset and would contaminate the baseline with post-stimulus signal.

## Three historical corpus-size vintages — do not mix

| Vintage | Sessions | Subjects | Units | Source | As-of |
|---|---|---|---|---|---|
| Legacy (pre-V182o) | 13 | 2 (C31o, V198o only) | 6,040 (`grand_database_6040_units.csv`) | `legacy/context/07_authoritative_data_topology_single_units.md` | undated, pre-2026-07-28 |
| Inventory | 23 | 3 | 9,228 (`unit_layers.csv` row count) | `context/inventory/{SESSIONS,UNITS,AREAS,CONDITIONS}.md` | 2026-07-28 |
| **Current** | **22** | **3** | **9,061** | `artifacts/data/corpus_manifest.json` + `artifacts/.lab/S1-unit-inclusion-rework-in-progress-20260817.json` | 2026-08-14/17 |

Arithmetic: 9,228 − 167 = 9,061 exactly. The single session `sub-C31o_ses-230630` (167 units,
present in the 23-session inventory) is **absent** from the current 22-session manifest — this is
almost certainly the entire explanation for the 23→22 session change, but the audit found no
explicit removal record; flagged in doc09. `outputs/layers/unit_layers.csv` shows this session's
`probe`/`unit_layer`/`crossover_channel`/`channel_area10` fields all blank.

Only the **22-session / 9,061-unit** vintage should be treated as current. Always name the source
file and its generation date next to any count you restate, per `omission-data` skill's explicit
instruction.

### 2026-07-28 inventory detail (for historical/background reference only)

`context/inventory/UNITS.md`: 9,228 units, 6,655 carry a functional class label in the sidecar
(2,573 do not). Sidecar functional-class breakdown: Other 4458 (66.99%), unlabelled 2573 (38.66%),
S+ 1432 (21.52%), S− 758 (11.39%), O+ 7 (0.11%) — **explicitly not the manuscript O+
classification** (that requires the Wilcoxon rank-sum p<0.01 criterion re-run fresh). Units per
area10: V1 824, V2 757, V3a/d 1110, V4 822, MT 1338, MST 290, TEO 778, FST 78, FEF 1124, PFC 2107.
Units per animal: C31o 3978, V182o 3188, V198o 2062. Binary `quality` field (1=4942, 0=4286) — this
binary scheme is **not** documented anywhere in the sidecars.

2026-08-17 rerun (`unit_inclusion_v1.csv`, 22 sessions, 9,061 units), a **different** 3-way
`quality_tier` scheme: `mua=4257, unstable=4026, stable=778`. Do not conflate with the older
binary `quality` field — they use the same column name in different places for different
semantics (CLAUDE.md tripwire #9: diff a same-named column on the overlap before joining).

## LFP artifact QC (2026-08-17)

`artifacts/.lab/supplement-lfp-artifact-qc-20260817.json` — percent trials excluded per animal:
Cajal 0.10%, Ivan 7.86%, Joule 2.09% (pooled), or 2.96% mean-of-sessions. Percent channels
excluded: Cajal 3.98%, Ivan 5.76%, Joule 8.95%. Cajal (C31o) has **no documented movement-artifact
pattern** in this corpus per `omission/jnwb_ext/artifact_repair.py`'s own receipt; Ivan (V182o) and Joule
(V198o) do.

## Existing data-topology documentation in the repo — status

| Doc | Status |
|---|---|
| `legacy/context/07_authoritative_data_topology_single_units.md` | Superseded — pre-V182o (13 sessions, 2 subjects), old drive layout (`D:/analysis/nwb`), background only |
| `context/inventory/{SESSIONS,UNITS,AREAS,CONDITIONS}.md` | Dated 2026-07-28, self-consistent internally, **superseded by the 22-session/9,061-unit vintage** above; regenerate via `scripts/build_corpus_inventory.py` before trusting again |
| `context/figures/fig01_recording_topology_and_paradigm/` | Current figure — actual recording-topology-and-paradigm figure, best visual reference |
| `context/handoff/2026-08-15-prgs-prepare/JNWB_API_INVENTORY.md`, `JNWB_ARCHITECTURE.md` | Dated 2026-08-15, recent; not deep-read by this audit — see [02_jnwb_api_reference.md](02_jnwb_api_reference.md) |
| This document | Synthesized 2026-08-17 from the sources above; supersedes none of them formally, cross-references all |
