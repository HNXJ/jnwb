# L0 — per-channel vs pooled omission LFP response [BLOCKER, spec §L0]

Reconciles Andre's "no omission LFP response in any area/band" against Hamed's "effect visible
per-channel, vanishes when pooled" by computing the omission response 4 ways on one
session/area/band: (a) per-channel power → pool linear → log once (correct, "log-last"), (b) pool
raw voltage across channels → then power (tests destructive interference/dipole cancellation),
(c) per-channel dB → average dB (the log-averaging bias `omission-signal` skill S1 warns about),
(d) CSD-referenced (`jnwb.spectral.laplacian_reference`) version of (a).

Run: `sub-C31o_ses-230823`, probe A, area FEF (single-area probe, 32-channel depth window,
local indices 48:80), band alpha (8–14 Hz), condition RXRR, n=55 trials.

**Result on this session/area/band: methods (a), (b), (c) agree** (−1.13, −1.10, −1.13 dB, CIs
heavily overlapping; (a)−(b) = −0.04 dB). Method (d), CSD-referenced, shows a smaller-magnitude
but same-sign effect (−0.83 dB). **This one cell does not reproduce Hamed's
vanishes-when-pooled pattern** — it is a single honest data point, not a general resolution of
the Andre/Hamed discrepancy, which would need sweeping across areas/bands/sessions before any
general claim is made.

`canonical_pooling_method = "a_per_channel_then_pool"` is a methodological determination (per
`omission-signal` S1), not something this one run could prove or disprove — L1–L12 must read
this field and fail loudly if absent, per spec.

Run `python L0_pooling_reconciliation.py --test` for the synthetic ground-truth self-test
(equal-and-opposite sup/deep dipole: real effect under (a), null under (b) — the spec's
acceptance criterion) before trusting any real-data run.

Outputs: `L0.svg` / `L0.png` / `L0.pdf`, `L0_stats.json`, `L0_manifest.json`.
