# 0.1.8

**Goal:** make the NWB onboarding workflow discoverable and executable without PyNWB plumbing
in user scripts:

`inspect → events/onsets → calibrated continuous/spike access → epoch extraction → analysis`

Evidence for review reconciliation: `python scripts/reconcile_review_probes.py` (receipt on
disk). §0–§6 (fixtures, inspect, events API, tutorials, docs/skills, harness gate 13) are
complete on `dev`; history is in git and `CHANGELOG.md`.

## Blockers (review reconciled — implement before seal)

### Processing-module LFP discovery and access

**Reproducer:** `ElectricalSeries` under `processing/ecephys/LFP` (no acquisition LFP).
`jnwb.inspect` → `acquisitions: []`; `acquisition_channel` → `AcquisitionNotFoundError`.

**Acceptance:** synthetic `processing_lfp_options()` fixture; `inspect` surfaces processing
continuous series; public resolve/read reaches `processing/ecephys/LFP`; matrix test for
inspect + `acquisition_channel`.

### Event extraction without a code column when not filtering

**Reproducer:** interval table with only `start_time`/`stop_time`. `event_onsets(...,
codes=None)` and `events(...)` → `ColumnNotFoundError` for default `code_column="codes"`.

**Acceptance:** `codes=None` ⇒ no code filtering; `code_column` required only when filtering
by `codes`; fixture + tests; docstrings/skill/README aligned.

### 1D `ElectricalSeries` channel access

**Reproducer:** single-channel series `data.shape == (n_samples,)`. `acquisition_channel(...,
channel=0)` → `ValueError: 2 indexing arguments for 1 dimensions`.

**Acceptance:** channel 0 works for 1D and `(n_samples, n_channels)`; out-of-range channel
raises a specific public error; fixture matrix entry.

### `conversion` / `offset` scaling (verify PyNWB first)

**Reproducer:** `ElectricalSeries(..., conversion=0.001, offset=0.5)`; PyNWB `series.data`
returns stored ADC counts; `acquisition_channel` returns same unscaled values.

**Acceptance:** establish PyNWB raw-vs-scaled semantics in test receipt; `acquisition_channel`
returns physically scaled values when attributes present; document `units`/scaling; no
double-apply.

### Continuous event epoching primitive

**Reproducer:** `examples/tutorials/03_align_spikes_lfp_to_events.py` uses manual
`i0 = int(onset_s * fs_hz)` index arithmetic after `acquisition_channel`.

**Acceptance:** public `epoch_continuous` (or equivalent) with explicit time/sample axis,
`fs`, onset units, pre/post window, output shape, boundary policy, NaN/padding; impulse +
boundary tests; Tutorial 3 rewritten to use it.

## Seal (after blockers)

- Version bump `0.1.7 → 0.1.8`; `CHANGELOG.md`; README pin
- Full pytest, harness gates 1–13, strict docs, API drift check, `release_gate.py`
- CI green on `dev`; promote to `main`; tag `v0.1.8`; GitHub Release before PyPI

## Review items classified not blocking 0.1.8

| Item | Verdict |
|---|---|
| PSTH `N=1` SEM | trade-off — `sem=0` by design; revisit Before 1.0 if NaN preferred |
| PPC at phase bound | not a defect — finite on probe grid |
| Short SOS `zero_phase=True` | documented trade-off — raises on very short signals |
| Low/high-pass wrappers, bulk access, spectral-axis changes, cluster-result redesign, phase-metric rename, ontology cleanup | deferred Before 1.0 unless new evidence blocks onboarding |

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
