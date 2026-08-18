# Handout: fig03 rework — retire legacy S classification, fix O++ boundary, diagnose O+ contamination

**From:** S1 session (unit-inclusion rework), for the fig03 session.
**UPDATE 2026-08-17 (Hamm, after reviewing the first version of this handout):** scope grew.
Verbatim: "at this point lets get rid of legacy ; hold on code accountable for all numbers used
in figure03 ; the one that ~1200+ and ~650+ are fine ; for O++ the 49 is correct ; O+ we gotta
see why is it 435 since im suspicious many are just S-/S-- appearing as O+". Three decisions now
locked in, in order below. This is no longer a small isolated change — **every number fig03
displays now needs to trace to a script, and the legacy template-correlation S+/S++/S-/S--
pipeline (`grand_s_and_o_units.csv` / `find_all_s_and_o_units.py`) is retired from fig03
entirely**, not just the O++ boundary.

## Request (Hamm, 2026-08-17)

> "we gotta adjust O+/O++ boundary so the panel f ; O++ mean, would be about ~50 neurons (that
> are, only in V4/TEO/FEF/PFC)"

Two changes to the O++ definition feeding panels B/E/F:
1. **Restrict area membership** to V4, TEO, FEF, PFC only (currently corpus-wide, all 9 areas).
2. **Tighten the correlation threshold** until the resulting count is ≈50 units.

## Where this lives

- `jnwb/unit_classification.py::OPlusPlusTemplateConfig` — the threshold config
  (`min_mean_correlation`, `max_permutation_pval`, `higher_order_areas`, `require_higher_order`).
- `jnwb/unit_classification.py::assign_o_plusplus_from_template_table()` — applies the config to
  `grand_oplus_units.csv` (the R-family template-correlation candidate table, columns include
  `area`, `mean_correlation`, `permutation_pval`).
- `scripts/build_oplusplus_census.py` — the pipeline script. **Currently line ~52 explicitly
  sets `require_higher_order=False`**, with a comment dated 2026-08-13 recording that this was
  *also* a direct request from Hamm at the time ("FEF/PFC was a validation hint to confirm the
  method... once confirmed, apply corpus-wide"). This handout is asking to partially reverse
  that — worth reading that comment before editing so the history isn't lost, and worth updating
  the comment (not just deleting it) to record this second change and why, per this project's
  Conservation convention (preserve the "why", don't silently overwrite prior rationale).
  Output: `outputs/classification/grand_oplusplus_units.csv` + `artifacts/data/oplusplus_census.json`.
- `context/figures/fig03_unit_census/fig03_unit_census.py`:
  - `attach_template_corr_oplusplus()` (~line 156) joins `grand_oplusplus_units.csv` onto the
    plotting dataframe as `is_oplusplus_tc`.
  - `panel_composition_oplusplus_by_area()` (~line 797) — **panel B**, O++ share of R-family
    candidates by area. Currently plots all 9 areas; will need its `areas` list narrowed to
    `["V4","TEO","FEF","PFC"]` (in `figstyle.AREA_ORDER` order) once the population itself is
    area-restricted, or the other 5 areas will just show 0/n bars — probably worth dropping them
    from the panel rather than showing empty bars, but that's a judgment call for whoever
    implements this to make and state explicitly in the receipt.
  - Panels **E, F** (grand-average O+/O++ traces) — need to check whether they already restrict
    to the O++-bearing areas or plot the O++ population pooled across whatever areas it contains;
    grep for where the E/F trace-building function selects its unit set (search
    `is_oplusplus_tc` and `panel_grand_average_by_condition` in this file) to confirm F's `n=`
    line will automatically reflect the narrowed population once `grand_oplusplus_units.csv` is
    regenerated, or whether it needs its own area filter too.

## Current state, verified just now (do not trust the numbers already printed on the rendered
## figure — they're stale relative to what's on disk right now, see below)

```
outputs/classification/grand_oplusplus_units.csv (current, r>=0.60 & p<=0.05, ALL areas): 144 units
  by area: V4=26 FEF=23 PFC=23 TEO=19 V2=17 V1=12 V3=8 MT=7 V3d=5 MST=2 V3a=2
```

**CORRECTION (2026-08-17, caught after Hamm asked for a recheck):** the figure currently
rendered shows "total: 129/359 O++ units" in panel B's title. I originally called this stale
relative to the 144 in `grand_oplusplus_units.csv` — that was wrong, verified by actually running
`attach_template_corr_oplusplus()` (fig03_unit_census.py:156) end to end: **129 is not stale, it's
the correct joined count.** The raw candidate table (`grand_oplusplus_units.csv`) has 144 rows,
but 15 of those don't find a matching row when joined onto `omission_grand_units.csv` (the
population fig03 actually plots against) — a real join-loss, not a pipeline-staleness issue. Both
144 and 129 are simultaneously live numbers; they just describe two different denominators (raw
candidate pool vs. post-join population). Worth understanding why those 15 don't join (likely a
session/unit-identity key mismatch between the two source tables) before or while making this
change — but it is NOT the "someone reran the pipeline and forgot to rebuild the figure" story I
originally guessed.

Also note: `grand_oplus_units.csv`'s own `area` column uses `V3`/`V3a`/`V3d` as three separate
labels, not the pooled `V3a/d` from `figstyle.AREA_ORDER` — irrelevant here since none of those
are in the V4/TEO/FEF/PFC target set, but worth knowing if the area-list code touches that
column directly.

## Threshold search — CORRECTED (see error note below before trusting any earlier version)

**ERROR CAUGHT 2026-08-17, after Hamm had already confirmed "49 is correct" based on the first
version of this table**: that "49" was a **row count** from `grand_oplus_units.csv`, not a
unique-unit count. 7 units in this candidate pool qualify under BOTH the `O+` (strict,
peak-dominance-gated) and `O*+` (looser, 2-of-9 template) pattern types simultaneously — each
appears as two separate rows, and a naive `.sum()` on the boolean mask double-counts them. The
actual unique-unit count at `r>=0.67` is **42**, not 49 — it does not clear Hamm's stated ≥50
floor. Corrected table, deduplicated on `(session_prefix, unit_row_idx)`:

| min_mean_correlation | unique units | by area |
|---|---|---|
| 0.60 (current) | 79 | V4=22 FEF=20 TEO=19 PFC=18 |
| 0.63 | 66 | V4=18 TEO=17 FEF=16 PFC=15 |
| **0.65** | **52** | **V4=15 PFC=14 TEO=12 FEF=11** |
| 0.66 | 47 | PFC=13 V4=13 FEF=11 TEO=10 |
| 0.67 | 42 | PFC=12 V4=12 FEF=10 TEO=8 |

**Corrected recommendation: `min_mean_correlation=0.65`** (not 0.67), `max_permutation_pval=0.05`
(unchanged), `higher_order_areas=("V4","TEO","FEF","PFC")`, `require_higher_order=True` — lands
at **52 unique units**, clears the ≥50 floor, area-balanced (11–15 per area). Whatever pipeline
code implements this (`build_oplusplus_census.py` / `assign_o_plusplus_from_template_table`)
must dedupe on unit identity before counting/plotting, or every downstream panel count (B's
share-by-area, F's `n=` line) will carry the same row-vs-unit inflation — check
`jnwb/unit_classification.py::assign_o_plusplus_from_template_table` and
`oplusplus_census_summary` for whether they already dedupe (grep for `drop_duplicates` /
`groupby` on the unit-identity columns) before assuming this is fixed elsewhere in the pipeline.

## O++ boundary: r=0.65 (52 units), NOT r=0.67/49 as previously stated

The row/unit-count bug above means the number Hamm confirmed ("49 is correct") was itself wrong
— Hamm was confirming a miscounted number. **Use `min_mean_correlation=0.65` → 52 unique
units**, not 0.67/49. This needs a fresh confirmation from Hamm once re-surfaced, not silent
substitution — flagging here rather than treating the original "confirmed" as still standing.

## O++ set (r>=0.67, the original — now superseded — 42-unit set) is ALSO contaminated

Checked whether the S-/S-- contamination found in the O+ pool (below) also taints the tighter
O++ set: of the 42 unique units at `r>=0.67`, **30 (71%) are also flagged legacy `is_Sminus` and
25 (60%) are `is_Sminus_double` (S--)**. Tightening the correlation threshold does not fix this —
it's the same scale-invariance problem as the general O+ pool, just applied to a smaller set.
Whatever population lands at ~50-52 units under the corrected threshold above almost certainly
carries the same contamination rate until the root-cause fix (below) is applied upstream.

## NEW: retire the legacy S+/S++/S-/S-- pipeline from fig03 entirely

Hamm, verbatim: "at this point lets get rid of legacy ; hold on code accountable for all numbers
used in figure03 ; the one that ~1200+ and ~650+ are fine". This replaces panel A's composition
source and every other panel that currently reads `grand_s_and_o_units.csv` /
`is_Splus`/`is_Splus_double`/`is_Sminus`/`is_Sminus_double` (produced by
`scripts/archive_oneoff/find_all_s_and_o_units.py`, template-correlation based, fx=0 in its O+
template — the exact mechanism S1 was built to move away from).

**New canonical S+/S- source: `outputs/classification/unit_inclusion_v1.csv`** (S1's output,
`jnwb/unit_classification.classify_unit`'s own local-baseline S+/S- — this was already carried
through S1's table unmodified, it was never the buggy mechanism, see
`artifacts/.lab/S1-unit-inclusion-rework-in-progress-20260817.json`). Confirmed numbers, computed
just now and matching Hamm's "~1200+ / ~650+" statement:

```
unit_inclusion_v1.csv, quality_tier != 'mua' (i.e. stable + unstable only):
  is_s_plus:  1211
  is_s_minus:  673
```

(Full corpus including mua: 1795 / 1077 — too high, Hamm's numbers match the **non-mua**
subset specifically, so `quality_tier in {stable, unstable}` is the population filter to use.)

**There is no S++/S-- (double-criterion) tier in this new source** — `unit_classification.py`'s
local-baseline classifier emits a single boolean `is_s_plus`/`is_s_minus` each, not a
single/double split. If fig03 still wants an S++/S-- visual distinction (panel A's current
`CLASS8_ORDER` has both), that tier needs either (a) a new criterion built on top of the S1
table (e.g., an effect-size or rate-magnitude cutoff within `is_s_plus==True` splitting it into
a stronger/weaker tier), or (b) dropping the double tier and switching panel A to a 6-class
scheme (S+/S-/O-/O--/O+/O++/Other). This is a design decision for the fig03 session /
Hamm to make, not something to invent silently — flag it rather than picking one.

**Scope of the retirement**: `(session, unit_row)` in `unit_inclusion_v1.csv` ↔
`(session_prefix, unit_row_idx)` in the legacy tables — same join key convention
`fig03_unit_census.py::attach_legacy()` already uses, so the join logic doesn't need to be
reinvented, only repointed at the new source table and its `is_s_plus`/`is_s_minus` columns
instead of the legacy ones. Every panel currently keyed off `legacy_screened`
(`attach_legacy()`'s `is_Splus.notna()` flag) needs its own screening definition reconsidered
too, since S1's table screens differently (it screens by `n_omission_events >= min_omission_events`
and quality/presence data availability, not by whether the legacy template-correlation test ran).

## NEW: O+ (435 candidates) — confirmed contamination by S-/S-- suppressed units

Hamm's suspicion, verbatim: "O+ we gotta see why is it 435 since im suspicious many are just
S-/S-- appearing as O+". **Checked directly, confirmed real** — full diagnosis in
`artifacts/.lab/bug-oplus-candidate-pool-suppressed-unit-contamination-20260817.json`. Summary:

- Of 359 unique units in the O+/O*+ candidate pool (`grand_oplus_units.csv`, 435 rows because
  some units qualify under both `O+` and `O*+` pattern types), **196 (55%) are also flagged
  `is_Sminus` and 154 (43%) are also `is_Sminus_double` (S--)** in the legacy table. Only 4 are
  also `is_Splus`.
- **Root cause, in `scripts/archive_oneoff/find_all_oplus_units.py` lines 187–205**: the O+/O*+
  gate is a Pearson correlation of the unit's 27-element (9 epochs × 3 conditions) rate vector
  against a one-hot/two-hot template, thresholded at `r>0.40` + permutation `p<0.05`. Pearson
  correlation is scale/sign-invariant — it only measures whether the omission slot sits
  *relatively* higher than the unit's other 8 epochs, not whether it's elevated above the unit's
  own overall/baseline rate. A broadly suppressed unit that happens to be *less suppressed* at
  the omission slot than elsewhere produces the same relative shape and passes. The only
  absolute-rate check in the script (line 173, `cond_rates[...] <= 0.0 → reject`) only requires
  nonzero firing, not baseline-relative elevation — far too weak to catch this.
- **This likely affects the O++ population too** (`grand_oplusplus_units.csv`, the confirmed-49
  set above) since it's drawn from the same contaminated `mean_correlation` column via a tighter
  cutoff — tightening `r` reduces candidate count, it does not fix a scale-invariance problem.
  Worth checking how many of the 49 confirmed O++ units are also flagged S-/S-- before treating
  49 as clean, not just as the right *count*.
- **Not fixed yet** — this handout only diagnoses it. A real fix needs an absolute-rate gate
  (omission-slot rate must exceed the unit's own overall/baseline rate by some margin, not just
  the other 8 epochs in its own vector) added to `find_all_oplus_units.py`, or an explicit
  exclusion of any candidate flagged S-/S-- by the new canonical S1 source above, before the O+
  count (435, or whatever population panels B/E/F end up using for "O+, not O++") can be trusted.
  This is a real analysis decision, not a mechanical config change like the O++ threshold — flag
  it to Hamm for the fix approach rather than picking one unilaterally.

## What this should NOT silently do

- Don't invent an S++/S-- tier definition on the new S1 source without asking (see above) — pick
  a documented, stated rule or drop the tier, don't guess at a magnitude cutoff quietly.
- Don't quietly "fix" the O+ contamination bug by picking an absolute-rate threshold without
  surfacing the choice — same reasoning, this changes what O+ means, not just how many pass.
- State every new threshold, area restriction, and source-table substitution explicitly in the
  figure's receipt (`fig03_receipt.json` / `svg/fig03_stats.md`) and in each pipeline script's
  own output JSON criteria block (CLAUDE.md tripwire #1 — no number without a receipt).
- Check `tests/` for coverage of `assign_o_plusplus_from_template_table`/
  `oplusplus_census_summary`/`attach_legacy` before assuming none exists; anything exercising the
  legacy S pipeline will need to be repointed or retired alongside it, not left silently broken.
