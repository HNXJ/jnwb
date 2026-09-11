# TODO stack

# 0.1.8

**Urgent, narrow release.** Make the core NWB workflow immediately discoverable and executable:

`inspect file → understand trials/events → extract onsets/data → run basic analysis`

Do **not** add unrelated analysis capabilities. Implementation starts only after this stack is explicit.

## 0. Structural authority receipt — **done** (`artifacts/nwb_structural_authority_0.1.8.md`)

Read-only survey complete (2026-09-11): omission-repo code/artifacts + h5py metadata on all 22 `D:\nwb\omission\` NWBs. `D:\nwb\mglo\` empty (no NWBs).

**Established structural classes (fixtures unblocked):**

| Class | Provenance table | Fixture |
|---|---|---|
| Task / omission-like | `/intervals/omission_glo_passive` | `test-synth-task` |
| RF-mapping-like | `/intervals/rf_mapping_v2` | `test-synth-rf` |
| Flash-like | `/intervals/flash` | `test-synth-flash` |

**API design requirements (not blockers):** explicit interval-table selection; primary code column `codes` (string-object or float64); `start_time` onsets in seconds; acquisition may be direct `ElectricalSeries` or `LFP` wrapper with nested `*_data`.

**Still unknown:** mglo corpus layout; omission-repo loaders for RF/flash tables (structure from disk only).

## 1. Canonical tiny synthetic NWB fixtures — **done** (`jnwb/testing/nwb_fixtures.py`, `tests/test_nwb_synthetic_fixtures.py`)

Package-owned, deterministic, reusable infrastructure (not tutorial throwaways). Neutral naming only.

**Shared constraints (all fixtures):**

- ~10 channels; 1000 Hz LFP sampling; ~10 trials/events; ~10 ms event/trial windows where structurally appropriate
- Few synthetic units/spikes; explicit electrode/channel metadata; explicit interval/trial tables
- Representative numeric and/or string event codes where the structural class uses them
- Deterministic signals with analytically obvious content (known onset times, separable condition codes)
- Labels: `test-synth-1`, `test-synth-2` (opaque; no experiment semantics)
- **Forbidden:** omission condition names, biological claims, subject IDs, cortical aliases, manuscript windows, project hypotheses

**Per-fixture targets:**

| Fixture | Structural class | Authority status |
|---|---|---|
| `test-synth-task` | Task-like: acquisition LFP + electrodes + units + task interval (`codes`, `task_condition_number`, …) | **Authorized** — `nwb_structural_authority_0.1.8.md` §C |
| `test-synth-rf` | RF-mapping-like interval (`codes`, `x_position`, `y_position`, `contrast`, `size`, …) | **Authorized** — §D |
| `test-synth-flash` | Flash-like interval (`codes`, `stimulus_number`, `task_condition_number`, …) | **Authorized** — §E |

**Implementation notes (when unblocked):**

- Add `jnwb/testing/` or `tests/nwb_fixtures/` builder module + `write_*` functions; generate `.nwb` in CI (do not commit large binaries if builder is sufficient)
- Builders must be importable for tutorials and wheel smoke tests
- Mirror real structural *shape* (acquisition paths, interval table names/columns, units linkage), not project semantics

## 2. `jnwb.inspect(path_or_nwb)` — **done** (`jnwb/nwb_inspect.py`, `tests/test_nwb_inspect.py`)

**Audit first:** no adequate public discovery API in `jnwb.__all__` today (`paths.describe()` ≠ per-file inspection; MCP `inspect_nwb` is not public).

**Smallest generic API:**

```python
info = jnwb.inspect(path_or_nwb)  # structured dict/dataclass, not text-only
```

**Must expose:** acquisitions (names, rates, shapes, time coverage), electrodes/channels metadata, units/spiking presence, interval/event/trial tables (names, columns, representative code/label values), shapes/dimensions, neurodata types where cheap.

**Human-readable display** derived from structured return; structured value is primary.

**Tests:** discriminating probes on all three synthetic fixtures once built; parity with known fixture contents.

**Export:** add to `jnwb.__all__`, regenerate `docs/api.md`, factor shared logic from `jnwb/mcp_server/nwb_tools.py` (MCP may wrap public API).

## 3. Canonical event/onset API — **done** (`jnwb/nwb_events.py`, `tests/test_nwb_events.py`)

Public workflow: `inspect` → `events` / `event_onsets`. MCP `get_event_codes_and_timings` wraps canonical primitives (MCP-only `code` column fallback preserved for backward compatibility).

**Exports:** `events`, `event_onsets`, `EventTable`, `resolve_interval_table`, `AmbiguousIntervalTableError`, `IntervalTableNotFoundError`, `ColumnNotFoundError`, `InvalidOnsetValueError`.

**Contract (docstrings + acceptance matrix):** explicit `table`; default `code_column="codes"`, `onset_column="start_time"`; seconds; row-order onsets; duplicates preserved; empty code selection → empty array; missing table/column → specific errors; NaN/non-finite onset → `InvalidOnsetValueError`; `trials` → sole table → ambiguity raise; no `"1"`/`1` coercion.

**LFP-wrapped HDMF warning:** corpus-observed for nested `LFP`/`ElectricalSeries` packaging (also on real omission NWBs); fixture structure not at fault.

## 4. Four fast executable tutorials — **done** (`examples/tutorials/`, `tests/test_tutorials.py`)

| # | Script | Scope |
|---|---|---|
| 1 | `01_inspect_nwb.py` | `jnwb.inspect` on canonical co-resident fixture |
| 2 | `02_event_codes_and_onsets.py` | codes discovery + `events` / `event_onsets` (task/RF/flash) |
| 3 | `03_align_spikes_lfp_to_events.py` | onsets → `raster_psth` + epoch `band_power` |
| 4 | `04_compose_workflow.py` | inspect → onsets → `compute_response_metrics` |

Shared I/O helpers in `examples/tutorials/_support.py` (single PyNWB read site). MkDocs/README nav wiring deferred to §5.

## 5. Documentation and skill alignment — **done**

- README NWB workflow (`inspect` → `events` / `event_onsets`); capabilities table updated
- MkDocs **Tutorials** nav; pages snippet-include `examples/tutorials/*.py`
- `skills/jnwb-nwb-data` routes to public API; `paths.describe` scoped to repo roots
- Public `unit_spike_times` / `acquisition_channel`; `_support.py` fixture-only
- LFP-wrapped fixture: register `LFP` on `NWBFile` before nested series (warning-clean)
- `tests/test_docs_nwb_workflow.py` (README execution, nav, skill, `mkdocs build --strict`)

## 6. Harness and release gate — **done**

- Tests: `test_tutorials.py`, `test_docs_nwb_workflow.py`, `test_nwb_events.py`, `test_nwb_synthetic_fixtures.py`, `test_nwb_inspect.py`
- Harness gate 13: `check_nwb_onboarding_alignment` (README / tutorials / skill / MkDocs)
- Gate 6 scan extended to `docs/tutorials/` and `examples/tutorials/`
- `release_gate.py` wheel smoke: synthetic NWB `inspect` → `event_onsets` → `unit_spike_times` / `acquisition_channel`

**0.1.7 gap:** symbol/gate coverage without executable onboarding path; closed by tutorial CI + gate 13.

## 7. 0.1.8 seal (after §1–§6 pass)

- Version bump `0.1.7 → 0.1.8`; `CHANGELOG.md`; README pin
- Full pytest, harness, strict docs, API drift check, `release_gate.py`
- CI green on `dev`; promote to `main`; tag `v0.1.8`; GitHub Release before PyPI

**0.1.8 acceptance (user-facing):** with only `pip install jnwb`, a new user can within minutes answer:

1. What is in this NWB?
2. What event codes/conditions exist?
3. How do I obtain their onset times?
4. How do I align spikes/LFP to those events?

…without reading PyNWB internals or any downstream project repository.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
