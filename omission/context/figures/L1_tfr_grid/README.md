# L1 — TFR grid, area x condition, fixation-baselined (Fig 4)

Reads `canonical_pooling_method` from [L0](../L0_pooling_reconciliation/L0_stats.json) and fails
loudly if missing/unexpected, per spec. Area x condition grid, one row per area, one column per
condition (`stim` = RRRR p1-aligned real presentation, `omission` = RXRR p2-aligned omission).
Power pooled per-channel-then-across-channels (L0's canonical method a), fixation-baselined
(-0.4 to -0.15 s pre-p1), log taken once. Symmetric diverging color scale shared across both
panels in a row, limits from the 2nd/98th percentile of the row's pooled zoomed values — per
spec's own acceptance criterion.

**Area substitution, stated not hidden**: spec's minimum area groups are V1/V2, MT/MST,
"8A/PFC". This corpus has no area labelled "8A" anywhere (checked directly against every nwb_ok
session's electrode table) — FEF and PFC both exist as real, distinct areas. Substituted FEF/PFC.

**Sessions** (one per area, not one per pair — TFR-per-area needs a channel range and a
condition set, not simultaneous recording of the pair; no single session in this corpus has
both FEF and PFC):

| Area | Session | Probe |
|---|---|---|
| V1, V2 | sub-V198o_ses-230629 | A |
| MT, MST | sub-C31o_ses-230818 | C |
| FEF | sub-C31o_ses-230823 | A |
| PFC | sub-C31o_ses-230818 | A |

32-channel depth window per area, ≤60 trials per condition (tractability caps, matching L0 and
`extract_lfp_coupling_matrices.py`'s existing conventions).

**Result, qualitative**: V1/V2/MT/MST show a strong, broadband (~20-100 Hz) power increase
following the real p1 stimulus — classic early visual evoked response. FEF/PFC show a much
smaller stim response with an alpha/beta (10-25 Hz) power *decrease* instead — consistent with
higher-order area desynchronization rather than an evoked increase. Omission responses are
present but weaker across the board; V1/V2's omission panel is thin (only 8 RXRR trials in that
one session — reported honestly in `L1_stats.json`, not smoothed over). This is descriptive
output for Fig 4, not an inferential claim — no p-values here.

Run `python L1_tfr_grid.py --test` for the synthetic-chirp ridge-recovery self-test (spec's own
acceptance criterion) before trusting a real run.

Outputs: `L1.svg` / `L1.png` / `L1.pdf`, `L1_stats.json`, `L1_manifest.json`.
