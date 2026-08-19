# L2 — band-power traces, band x area, session-bootstrap CI (Fig 5)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json), same gate
as L1. Grid: 5 house bands (rows) x 6 areas (columns; FEF/PFC substituted for spec's stale
"8A/PFC", see L1's README). Each panel overlays stim (solid) and omission (dashed), pooled trace
+ shaded 95% **session-level** bootstrap CI (`n_boot=2000`, seed 42) — **not** trial-level, per
the spec's explicit prohibition (trial-level bootstrapping inflates precision by ignoring
between-session variance; see the self-test, which asserts the session-CI is >3x wider than a
naive trial-scale CI on the same synthetic data). Thin colored lines are per-subject means
(no individual CI — 2–6 sessions per subject is too few to trust a subject-specific CI on its
own; read the shaded pooled CI quantitatively, subject lines qualitatively).

**Log-last applied twice** (channel pooling from L0's method (a), then again across a band's own
frequency bins) — averaging already-log'd per-bin dB values across a band would repeat the exact
bias `omission-signal` S1 warns about; this script never does that (see module docstring).

**Real per-subject coverage** (survey against every session's own electrode table, not assumed):
V1/V2 ← C31o + V198o; MT/MST/FEF/PFC ← C31o + V182o. Every area in this run has genuine 2-subject
coverage — up to 6 sessions per area (capped at 3/subject).

**Qualitative result**: V1/V2/MT/MST show large, consistent stim-evoked broadband power increases
(gamma bands especially, 5–15 dB) with omission responses present but smaller — consistent with
L1's TFR grid. FEF/PFC show much flatter, noisier traces with substantial between-session/subject
variance (wide shaded CIs) — no clean band-specific evoked structure in this run. This is
descriptive output for Fig 5, no p-values.

Run `python L2_band_power_traces.py --test` first (synthetic multi-session dataset with known
population mean and between-session variance — checks CI coverage and confirms the session-CI is
not accidentally collapsing to trial-level width).

Outputs: `L2.svg` / `L2.png` / `L2.pdf`, `L2_stats.json`, `L2_manifest.json`.
