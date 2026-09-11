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

## 3. Canonical event/onset API

**Audit inventory (before coding):** NWB `trials`, interval tables, event tables, `start_time`/`stop_time`, metadata/addressing filters, MCP `get_event_codes_and_timings`, decoding trial tables, `EpochCollection`, `detect_trial_cycles` — document what stays internal vs becomes public.

**Required public route:**

`NWB → interval/event table → code column → select code(s) → onset timestamps`

**Contract must document:**

- table selection and ambiguity behavior (inherit `trials` → sole table → explicit path → error)
- code/label column selection (explicit param; no silent guess beyond documented fallback order)
- numeric and string codes
- onset column (default `start_time` only when justified; other timestamp columns explicit)
- seconds, session/time reference, ordering, dtype
- duplicates, empty selections, missing table/column/code
- multiple interval tables
- **Never infer scientific meaning from code values**

**Smallest API shape (design in code review):** likely `list_interval_tables`, `read_interval_table`, `event_onsets(nwb, table=..., codes=..., code_column=..., onset_column='start_time')` — exact names TBD; must be one obvious documented path.

**Tests:** same API across task, RF-like, and flash-like fixtures; all ambiguity/failure cases; analytically known onset times in synthetic data.

## 4. Four fast executable tutorials

CI-friendly; run from clean installed wheel; use synthetic fixtures only.

| # | User question | Scope |
|---|---|---|
| 1 | What is in this NWB? | Load each tiny fixture; `jnwb.inspect`; interpret structured output |
| 2 | What codes exist and what are their onsets? | Discover tables/codes; select `test-synth-*`; retrieve onset times via §3 API |
| 3 | How do I align spikes/LFP to events? | Retrieved onsets → existing `raster_psth` / `band_power` (or minimal equivalent) |
| 4 | How do primitives compose? | inspect → select → align → one small spectral/spiking/statistical operation; no imposed study pipeline |

**Acceptance:** `tests/test_tutorials.py` (or equivalent) executes all four; no PyNWB plumbing duplicated in tutorial source; no private/downstream repo.

## 5. Documentation and navigation

- **README:** first-user path immediately after install:

  ```python
  import jnwb
  info = jnwb.inspect("file.nwb")
  # → canonical event/onset workflow (§3 API)
  ```

- **MkDocs:** add prominent **Tutorials** section to `mkdocs.yml` nav; four tutorial pages
- **API reference, tutorials, README, `skills/jnwb-nwb-data`:** same public path and terminology (no `paths.describe()` as "inspection")
- Update `docs/quickstart.md` to point at tutorials for NWB workflows; keep synthetic-array quickstart where appropriate

## 6. Harness and release gate

Add deterministic proofs that:

- all synthetic NWBs build and read
- tutorials execute (local + installed-wheel job where feasible)
- `jnwb.inspect` accurately reports fixture structure
- event/onset extraction returns analytically known timestamps
- fixture contents and tutorials contain no downstream-project identifiers
- documentation acceptance: principal workflow `public capability ⇒ API reference + executable tutorial path`

Wire into `tests/`, `harness_gate.py`, and/or `release_gate.py` as appropriate. Diagnose why 0.1.7 seal did not catch missing onboarding (symbol/gate coverage without workflow tutorial).

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
