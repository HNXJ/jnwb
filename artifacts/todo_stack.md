# 0.1.8

**Goal:** make the NWB onboarding workflow discoverable and executable without PyNWB plumbing
in user scripts:

`inspect → events/onsets → calibrated continuous/spike access → epoch extraction → analysis`

Evidence for review reconciliation: `python scripts/reconcile_review_probes.py` (receipt on
disk). §0–§6 (fixtures, inspect, events API, tutorials, docs/skills, harness gate 13) are
complete on `dev`; history is in git and `CHANGELOG.md`.


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
