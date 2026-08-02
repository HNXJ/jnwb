# Plan (not started): sliding-window connectivity, LFP-LFP and spike-LFP

**Status: locked as a plan on 2026-07-30, explicitly deferred by the user until figures 1-5 are
reviewed as finalized.** No code exists for this yet. Referenced from both
`fig06_band_power_coupling/README.md` and `fig07_lfp_spike_coupling/README.md` rather than
duplicated in each, since it applies identically to both.

## The core insight: RXRR, RRXR, RRRX share a common realignable sub-sequence

Every omission slot (p2 in RXRR, p3 in RRXR, p4 in RRRX) is immediately preceded by a REAL
stimulus. Because every p/d epoch has the same duration (~500-531 ms per
`jnwb.sequence_layout.EPOCH_ONSETS_MS`), re-aligning each condition to *the real stimulus
immediately before its own omission* (not always p1) collapses all three conditions onto an
IDENTICAL local structure: **delay - real p (t=0) - delay - omitted p - delay**. Concretely,
relative to that local t=0:

| condition | absolute omission slot | local "real p" | relative structure (ms) |
|---|---|---|---|
| RXRR | p2 | p1 | d(fx,-500) - p(0) - d(531) - **omitted p(1031)** - d(1562) - next real p(2062) |
| RRXR | p3 | p2 | d(d1,-500) - p(0) - d(531) - **omitted p(1031)** - d(1562) - next real p(2062) |
| RRRX | p4 | p3 | d(d2,-500) - p(0) - d(531) - **omitted p(1031)** - d(1562) - *(no next real p in-trial)* |

The same realignment applies within the A and B families: AXAB/AAXB/AAAX share the identical
local structure via their own family's real-p-before-omission, and likewise BXBA/BBXA/BBBX.
This is what lets RXRR+RRXR+RRRX (or the A-family or B-family equivalents) be POOLED into one
larger trial set for a given family, instead of using RXRR alone the way figures 6/7 do today —
more trials per family without touching cross-family comparisons.

**Open edge case, not yet resolved**: RRRX (and AAAX, BBBX) have no real stimulus after the
omission within the same trial (p4/d4 is the last epoch) — the "next real p at +2062" column
in the table above doesn't exist for these three conditions. The window below only needs
through +2000 ms, which stays inside p4's own delay for all three families, so this doesn't
block the plan, but any panel wanting to show "response to the next real stimulus" would need
to special-case these three conditions or accept they contribute one fewer post-omission data
point than RXRR/AXAB/BXBA.

## Window

Full local window per the realignment above: **[-500, 2062] ms** (the "d-p-d-px-d" span, using
the next epoch's onset as the end boundary — same convention as figure 4/5/6/7's existing
`CONDITION_WIN`/`P2_WINDOW_MS`). **Narrowed to [-400, 2000] ms** for the sliding-window analysis
specifically, to keep every 400 ms analysis frame's band-pass filter edge inside the window and
away from the true epoch boundaries (same motivation as `extract_spike_lfp_coupling.py`'s
`PAD_S` padding, applied here by trimming the outer 100 ms on each side instead).

## Sliding frames

`w = range(-400, 2000, 100)`, each frame `(w, w+400)` — 400 ms width, 100 ms step (300 ms
overlap between consecutive frames). **Frame count needs reconciling before this is built**:
computed directly from the stated range/step, this gives frames starting at -400, -300, ...,
1600 (21 frames total, last one `(1600, 2000)`), not the 25 the message named — the discrepancy
should be resolved (against the exact intended step/width, or a possibly-intended narrower step
such as 64 ms) before any frame index is treated as authoritative in a figure or receipt.

## Family separation rule (do not relax without a stated reason)

**Each frame's connectivity/coherence is computed within one family only**: R-family
(RXRR+RRXR+RRRX pooled via the realignment above), A-family (AXAB+AAXB+AAAX pooled), B-family
(BXBA+BBXA+BBBX pooled) — three separate "connectivity videos," never mixed. Comparing across
families (e.g. does AX coupling differ from RX coupling) is explicitly a SEPARATE, later
analysis, not folded into this one — avoids the false-positive/false-negative risk of pooling
trial types whose only common feature is "there was an omission somewhere in the trial."

## Metrics per frame

Coherence (`jnwb.spectral.imaginary_coherency`, already built and validated for figure 6),
correlation, and power correlation ("power corr") are all named as candidates — this plan does
not yet pick one exclusively; the eventual build should state which (or which combination) and
why, following this project's "minimize the diversity of tests" doctrine rather than running
all three by default.

## Relationship to figures 6 and 7 as they stand today

Figures 6/7 currently use only two fixed windows (stimulus: p1, 0-531 ms; omission: p2 in RXRR
only, 1031-1562 ms) — single snapshots, not a time-resolved sequence, and RXRR only (not
pooled with RRXR/RRRX). This plan is a genuine methodological upgrade: same estimator
(`imaginary_coherency` for LFP-LFP, PPC for spike-LFP), same re-referencing and null-shuffle
machinery, applied to a sliding window across the realigned family-pooled trial set instead of
two fixed windows on one condition. Not started; do not begin implementation until told to.
