# Drift checklist — figs 1-7 + supplements

Generated 2026-08-04 by reconciling `INVENTORY.md`, `README.md`, `HANDOUT_NEXT_AGENT_2026-08-03.md`,
`build_supplements.py`'s `PLAN`, `artifacts/.lab/seal_checkpoint_*`, and the actual files on disk.
**Two of those sources were already stale when checked — see "Drift found" below.** Re-run this
reconciliation (don't just re-read this file) after any figure script or `build_supplements.py`
edit; it decays the same way `INVENTORY.md` warns about.

## Main figures 1–7

| # | Locked (`fig0N_finalized.svg/.png`) | Committed | Analysis code | Notes |
|---|---|---|---|---|
| 1 | ✅ yes | ✅ `912a0a4`-line history | yes | — |
| 2 | ✅ yes | ✅ | yes | 4x4 raster grid, O++ column manually overridden to unit 51/FEF (documented in script) |
| 3 | ✅ yes | ✅ | yes | presence + functionality + RXRR template trace |
| 4 | ✅ yes | ✅ `912a0a4` "fig04: lock finalized figure with contract mean/SEM display" | yes | **Locked 2026-08-03 16:01** per `artifacts/.lab/seal_checkpoint_20260803_fig04_locked.json`. Contract mean/SEM display kept; an unauthorized median-estimator experiment was rejected and quarantined outside the repo (recoverable, not deleted). |
| 5 | ❌ not locked | n/a | yes | No `fig05_finalized.*`. `fig05.svg` exists, last standalone build per handout. **Not reviewed this pass — pick up next.** |
| 6 | ❌ not locked | n/a | yes | No `fig06_finalized.*`. Corpus result: 0/240 survive correction (Holm and BH) in both windows — see `fig06_band_power_coupling/README.md`. |
| 7 | ❌ not locked | n/a | yes | No `fig07_finalized.*`. Corpus result: 0/60 significant — see `fig07_lfp_spike_coupling/README.md`. |

**Falsifier for "figure done":** `context/figures/fig0N_finalized.svg` and `.png` both exist,
were produced via the headless-Chrome white-background render, and the user has explicitly
confirmed panel content (not just that a file exists). Figs 1–4 meet this; 5–7 do not.

## Supplementary figures

**Formal registry (`build_supplements.py`'s `PLAN`) declares exactly 23 supplements, S01–S23,
0 pending.** All 23 are present on disk under `context/figures/supplements/`. The user's request
named "supp figures 1-14" — that undercounts what's actually in the registry; treat 23 as the
current true count, not 14, and flag this mismatch to Hamm rather than silently building to
either number.

| Range | Count | Source figure | Status |
|---|---|---|---|
| S01–S02 | 2 | fig01 | on disk, in PLAN |
| S03–S04 | 2 | fig03 | on disk, in PLAN |
| S05–S16 | 12 | fig04 (old area×layer, omission-pooled content) | on disk, in PLAN |
| S17–S19 | 3 | fig05 (old omission-pooled hierarchy) | on disk, in PLAN |
| S20–S21 | 2 | fig03 | on disk, in PLAN |
| S22 | 1 | fig06 (stimulus-window coupling) | on disk, in PLAN |
| S23 | 1 | fig07 (stimulus-window PPC) | on disk, in PLAN |

### Drift found: two files exist outside the formal PLAN

- `figS24_omission_identity_decoding.svg/.png` — has its own script
  (`figS24_omission_identity_decoding.py`) and its own `.lab` receipt
  (`supp_figS24_omission_identity_decoding_20260802.json`, confirmed 2026-08-02). **Not added to
  `build_supplements.py`'s `PLAN`.** Running `build_supplements.py` (no `--list`) deletes any
  `supplements/figS*` file not named by `PLAN` before writing — **this file would be silently
  deleted by the next supplement rebuild** unless added to `PLAN` or the deletion logic is told
  to spare it.
- `figS_v182o_condition_bandtraces.svg/.png` — not `S`-numbered at all, has its own receipt
  (`figS_v182o_condition_bandtraces.receipt.json`, 2026-07-31) from
  `scripts/plot_v182o_condition_bandtraces.py`. Same exposure: not in `PLAN`, will not survive a
  clean rebuild, and isn't counted in "23 supplements" anywhere.

**Action needed, not yet taken:** decide whether S24 and the v182o trace are (a) folded into
`PLAN` as S24/S25 so they survive rebuilds and are covered by `INVENTORY.md`'s auto-generation,
or (b) archived out of `supplements/` if they're one-off/exploratory and not meant to ship. Until
one of those happens, the registry and the directory disagree — the exact "registry goes stale
silently" failure mode this repo's own doctrine warns about.

## Drift found in existing docs (already stale before this checklist)

1. **`HANDOUT_NEXT_AGENT_2026-08-03.md` (written 2026-08-03 11:05) says fig04 is "in progress,
   not yet locked."** It was locked later the same day at 16:01
   (`seal_checkpoint_20260803_fig04_locked.json`, and `fig04_finalized.*` committed in `912a0a4`).
   The handout is now stale on its central claim — don't trust it for fig04 status; this
   checklist supersedes it there. (It remains untracked in git; whether to commit or retire it
   is still an open call per the seal's own "issues" list.)
2. **`context/figures/README.md` (committed 2026-08-01, same commit as `INVENTORY.md`) says
   fig06 and fig07 have "no" code and "analysis not written."** This was already false in the
   same commit: `fig06_band_power_coupling.py` / `fig07_lfp_spike_coupling.py` exist, each has a
   README describing a completed, corrected, corpus-wide build from 2026-07-30, and
   `INVENTORY.md` (generated by script, same commit) lists real statistics families and
   supplement feeds for both. `README.md`'s hand-maintained status table was not updated when
   figs 6/7 landed — trust `INVENTORY.md` over `README.md`'s status table for figs 6/7.

## What "no drift" requires going forward

- [ ] Fig 5: build `fig05_finalized.svg/.png` via the same headless-Chrome white-background
      method, get explicit user confirmation of panel content, write a seal checkpoint.
- [ ] Fig 6: same three steps.
- [ ] Fig 7: same three steps.
- [ ] Resolve S24 / v182o registry gap (fold into `PLAN` or archive).
- [ ] Fix `README.md`'s status table for figs 6/7 (or better: stop hand-maintaining a status
      table that duplicates what `INVENTORY.md` already derives, and point readers at
      `INVENTORY.md` instead).
- [ ] Decide + record disposition of `HANDOUT_NEXT_AGENT_2026-08-03.md` (commit as historical
      record, or delete now that fig04 is locked and its content is superseded by this file).
- [ ] After any of the above, re-run `python build_inventory.py` and `python build_supplements.py`
      (no `--list`) so `INVENTORY.md` and `supplements/` reflect reality again, then re-check this
      checklist rather than assuming it still holds.
