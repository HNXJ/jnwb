---
name: omission-data
description: >-
  TRIGGER before opening an NWB file, resolving a data path, selecting trials or units, or
  joining any two tables. Covers jnwb.paths, OmissionSession access, condition/phase codes,
  unit quality tiers, and the identity footguns (row position vs unit_id, dual-area probes,
  bytes-encoded h5py columns). Load before the first read, not after a count looks wrong.
---

# omission-data

**ROUTING_SENTINEL:** `omission-data:v1`

> Acceptance-test marker. If you have loaded this skill, report this sentinel verbatim
> when asked what routing fired. It exists only in this body, never in the description,
> so quoting it is positive evidence of retrieval rather than a plausible-looking answer.

**Owns:** paths and roots · session I/O · condition and phase codes · unit quality tiers ·
electrode and channel addressing · table joins.

## Resolve paths, never hardcode

```python
import jnwb as oa
oa.paths.describe()        # every root + whether it currently resolves -- run this first
oa.paths.REPO_ROOT         # from the package's own location; always correct
oa.paths.nwb_dir()         # $OMISSION_NWB_DIR       (read-only inputs)
oa.paths.analysis_dir()    # $OMISSION_ANALYSIS_DIR  (all derived data)
oa.paths.tfr_dir()         # $OMISSION_TFR_DIR
oa.paths.meta_dir()        # $OMISSION_META_DIR
oa.paths.outputs_dir(...)  # repo-relative
oa.paths.require(p, "NWB directory", "OMISSION_NWB_DIR")   # exists-or-raise, with the fix
```

Two classes of root and they fail differently. **Repo-internal** roots derive from `__file__`
and cannot drift. **External data** roots live on a separate volume that moves; if `describe()`
reports `exists: false`, set the env var. Do not edit source and do not write a new absolute
literal into a script — a drive remap once broke every hardcoded path at once, silently,
because they were default arguments resolving to a nonexistent path rather than raising.

Derived artifacts never go into the repo. A sibling NWB tree for a **different experiment**
exists next to this one — never glob across the parent directory or you will pull foreign
sessions into an omission analysis. Resolve the corpus with `scripts/discover_corpus.py`
rather than trusting a remembered file count.

## Corpus size is discovered, not remembered

Do not quote a session count, unit count, or TFR file count from this file, from a handout, or
from memory. Run:

```bash
python scripts/discover_corpus.py --check
```

Exit `0` resolved and passing · `1` resolved with a blocking mismatch · `2` discovery failure.
Every number in a report names the manifest run that produced it. Numbers that appear in older
material ("21 sessions", "8,592 units", "13 sessions", "6,040 units", "23 sessions /
1,236 TFR files") are historical and must be re-derived before restatement.

## Loading

```python
session = oa.read(oa.paths.nwb_dir() / 'sub-C31o_ses-230823_rec.nwb')
sessions = oa.batch_read(oa.paths.nwb_dir(), pattern='*.nwb')

session.info(); session.summary()
units_df = session.get_units(quality='stable_plus', area='V1')
elec_df  = session.get_electrodes(area='V4')
epochs   = session.get_epochs(phase=3, condition='AAXB', correct_only=True)
lfp_map  = session.lfp_channel_areas()
unit_map = session.channel_unit_mapping()
```

**Correct trials only by default.** `nwb.intervals["omission_glo_passive"]` is event-level, not
trial-level.

## Condition codes

| Name | Condition numbers | Meaning |
|---|---|---|
| AAAB | 1, 2 | all A, B deviant at p4 — **the structured standard, not a random control** |
| AXAB | 3 | omission at p2 |
| AAXB | 4 | omission at p3 (canonical omit) |
| AAAX | 5 | omission at p4 |
| BBBA | 6, 7 | all B, A deviant at p4 |
| BXBA / BBXA / BBBX | 8 / 9 / 10 | B-family omissions at p2 / p3 / p4 |
| RRRR | 11–26 | random control |
| RXRR | 27–34 | random, omission at p2 |
| RRXR | 35, 37, 39, 41 | random, omission at p3 (**odd slots only**) |
| RRRX | 36, 38, 40, 42–50 | random, omission at p4 |

**Subject V182o uses a different map** (`CONDITION_MAP_V182O` in `jnwb/session.py`):
RRXR = 35–42, RRRX = 43–50, contiguous with no odd/even split. Always resolve from the map
dict, never from memory — the default map's odd-slot RRXR split has silently mislabeled
sessions.

`stimulus_number` is the stable crosswalk for slot selection: p1=2, p2=3, p3=4, p4=5, fixation=1
(`phase` argument = the same integer). Do not confuse BHV odd event codes with NWB sequential
event codes.

## Unit quality tiers

| Quality | Definition |
|---|---|
| `stable_plus` | `is_stable` and FR > 1 Hz and SNR > 0.8 and 100% trial presence |
| `stable` | `is_stable` but not stable_plus |
| `mua` | multi-unit activity |
| `unstable` | poor quality / unstable |

Alternative operational definitions also live in the corpus (kilosort `quality == 1.0`;
`presence_ratio >= 0.98` + FR > 0.5 + SNR > 0.5). **Say which definition a number uses.**
Ten ordered analysis areas: V1, V2, V3a/d, V4, MT, MST, TEO, FST, FEF, PFC.

## Metadata and diagnostics

```python
from jnwb import (get_all_units_metadata, classify_unit_quality, unit_census_report,
                  get_snr_analysis, electrode_inventory,
                  audit_session, compare_sessions, print_audit_report)
```

## Footgun: unit identity is a row position, not `unit_id`

`session.get_spike_times(i)` indexes by **DataFrame row position**, not the `unit_id` column.
`unit_id` is a per-probe-local kilosort id with gaps, not globally unique. Passing a `unit_id`
value where a row position is expected silently fetches the wrong unit's spikes — a confirmed
real bug in `jnwb/trajectory.py::build_time_resolved_matrix` and in a consumer script. Assert
before indexing:

```python
assert units.loc[row, 'unit_id'] == target_ks_id, f"row {row} is {units.loc[row,'unit_id']}"
```

## Footgun: dual-area probes resolve by channel position

A probe labeled `"Y, Z"` or `"Y/Z"` means channels 1–64 = Y, 65–128 = Z. Bare `"V3"` expands to
`(V3d, V3a)`; dual `"V3, V1"` keeps V3 as the first half with no expansion. **Never resolve area
by `location.split(',')[0]`** — that shipped once and mislabeled 1,965 of 6,655 rows in the
grand unit table. Use `jnwb.addressing.map_peak_channel_to_area`.

## Footgun: bytes-encoded h5py columns

On some sessions raw intervals-table columns read via h5py come back as byte strings (`b'2.0'`,
`b'nan'`). Naive numeric comparison silently produces wrong trial counts (370 vs a real 246 on
one condition). Prefer `session.get_epochs(...)`; if you must read raw, coerce with a
bytes-aware parser and sanity-check trial counts.

## Footgun: direct h5py layout differs by subject

Some sessions block a full PyNWB build. LFP group layout is **not** uniform:

- C31o: `acquisition/probe_0_lfp/{data,electrodes,timestamps}`
- V182o: `acquisition/probe_0_lfp/probe_0_lfp_data/{data,timestamps}`
- pupil: `acquisition/pupil_1_tracking/...` — there is no `pupil_diameter` group
- there is **no** `electrical_series` intermediate group in these files

Probe indices run 0–2 (some sessions 0–3). Verify per file; do not assume.

## Footgun: a field with the same name in two tables is not the same field

`grand_stable_firing_rates.csv` carries its own `quality` column, separate from
`omission_grand_units.csv`. They disagree on 1,942 of 6,650 shared units (29%);
`outputs/layers/unit_layers.csv` agrees with the grand table on every one of those, so the
stable-rates copy is stale relative to a later re-sort. **Diff any same-named join column on the
overlap before joining.**

## Footgun: check a column varies before interpreting it

All 6,655 screened units in one classification pass carry `layer = Superficial`. Any laminar
statement drawn from that field describes a default, not anatomy.

## Structured objects and provenance

When an analysis should carry its own provenance rather than return a bare dict, build it from
`jnwb.ontology` via `jnwb.factories` (`dataset_from_session`, `aligned_dataset_from_dataset`,
`epochs_from_aligned_dataset`, `result_from_*_analysis`, `figure_from_result`).
`Provenance`/`Lineage` make a `Result` traceable to its data source, parameters, and code — use
them rather than reconstructing provenance later.

## MCP server

`jnwb.mcp_server` exposes `inspect_nwb` (not `inspect_nwb_file`),
`get_event_codes_and_timings`, `prepare_signal_reference`, and `add_tool` (gated behind
`ALLOW_DYNAMIC_TOOLS`, off by default). Pinned to `mcp<2.0`.
