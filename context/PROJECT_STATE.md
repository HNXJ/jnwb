# PROJECT_STATE.md — omission-a

**What this file is:** the current scientific and repository state. It answers *what is true
now*, not *what to do*. **It contains no instructions to any agent.** Behavioral rules live in
`CLAUDE.md` and the skills; evidence semantics live in `EVIDENCE_ARCHITECTURE.md`.

**Every number below carries the date it was resolved.** Counts and paths are observations with
a shelf life — re-resolve from `artifacts/data/corpus_manifest.json` rather than citing this
file as authority for a count.

**Last resolved:** 2026-08-15 (onset-hierarchy boundary-pinning fix, §4; RNG-determinism fix for
the two classify scripts, §1).

---

## 1. Corpus — and an unresolved inconsistency

| Quantity | Value | Source | Resolved |
|---|---|---|---|
| NWB sessions | **22** | `artifacts/data/nwb_catalog.json` (`n_files`) | 2026-08-11 |
| NWB directory | `D:\nwb\omission` | same (`nwb_dir`) | 2026-08-12 |
| Subjects | C31o, V182o, V198o | `session_readiness.csv` | 2026-08-12 |
| Readiness rows / `nwb_ok` | 22 / 22 | `session_readiness.csv` | 2026-08-12 |
| **`tfr_ok`** | **22 of 22** | `session_readiness.csv` | 2026-08-14 |
| `suite_tfr_ready` | 0 of 22 (separate, unresolved -- see below) | `session_readiness.csv` | 2026-08-14 |
| TFR array files on disk | 970 | `D:\analysis\tfr_arrays` | 2026-08-12 |

### RESOLVED 2026-08-14 — TFR readiness gate was unsatisfiable due to two stale scan bugs

The `tfr_ok=0/22` gate was never a real data problem. Two independent scans both attributed TFR
files to sessions using patterns that predated the `.npy`→`.npz` migration and the 4th probe
letter (`scripts/precompute_tfr_arrays_v2.py`, begun 2026-08-11):

1. `scripts/build_session_readiness.py`'s `tfr_index()` globbed only `*.npy` and matched only
   probe letters `[ABC]`; the corpus is 970 `.npz` files with probes A/B/C/D. Fixed.
2. `scripts/discover_corpus.py`'s `_scan_tfr()` matched TFR filenames against the raw NWB
   filename `stem` (which keeps a trailing `_rec` for most C31o/V198o sessions), but TFR
   filenames are built from `session_prefix` (`_rec` already stripped) and never carry `_rec` --
   so it silently undercounted to 10/22. Fixed to match on `session_prefix`, consistent with
   `nwb_catalog.json`'s own field of that name.

Verified: `python scripts/build_session_readiness.py` now reports `tfr_ok=22/22`;
`python scripts/discover_corpus.py --check` exits 0 with no blocking mismatches (only a separate
`metadata_dir`-unresolved warning, see below). Each `.npz` file is self-contained (`power`,
`channels`, `fit_exponent`, `fit_r2` — verified on `sub-C31o_ses-230816-A-PFC-RXRR.npz`), so a
TFR-consuming analysis does not need the sidecar directory to use this corpus.

### Still open — `sidecar_ok` / `suite_tfr_ready` (separate issue, not the one above)

`sidecar_ok=0/22` because `jnwb.paths.meta_dir()` resolves to `D:\analysis\metadata`, which does
not exist on this machine. Unlike the TFR fix above, this is not diagnosed as a stale-pattern
bug — no metadata sidecar directory was found anywhere on disk in a shallow search, so this may
reflect sidecars never having been (re)generated for the current corpus rather than a wrong path.
Not investigated further as of 2026-08-14. Any pipeline that actually needs
`electrodes.csv`/`units.csv`/`events.csv`/`h5_paths.json` sidecars (as opposed to what's already
embedded in each session's NWB file or each TFR `.npz`) is still blocked; a TFR-only analysis
that gates on `tfr_ok` rather than `suite_tfr_ready` is not.

### RESOLVED 2026-08-14 — the p2-omission-vs-real condition-map GLMM was built from the superseded TFR path

`outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz` (input to
`context/figures/fig06_v1_pfc_condition_tfr/fig04_glmm_all_areas_timeresolved.py`) carries a
`receipt.json` showing it was generated **2026-08-04** from `source_dir=D:/workspace/data/tfr_arrays`
— one of the superseded paths listed just below. That predates both the TFR path migration and the
2026-08-11 `.npy`→`.npz` / 1/f-quality-screening rebuild, so the GLMM run built on it (lab node
`fig04-glmm-all-areas-timeresolved-20260813`, was `status: confirmed`) does not reflect the current
corpus. Found while resolving the `tfr_ok` gate above, per the `labyrinth` skill's "re-verify
independently rather than inheriting a prior seal's verdict."

Regenerated: `scripts/extract_condition_tfr_maps_v2.py` (new file; the old script's position-based
channel indexing is wrong for the new corpus, whose channel axis is already screened per file — see
the script's own docstring) →
`outputs/condition_tfr_maps_p1d1p2d2p3_v2/maps.npz` (485/485 files, 0 skipped, 900 keys, all 11
areas, `source_dir` now correctly `D:\analysis\tfr_arrays`). Rerun GLMM:
`fig04_glmm_all_areas_timeresolved_v2.py` → `outputs/fig04_glmm_all_areas_timeresolved_v2/`.

**Q1 (is it an omission? `db~C(context)`) replicates but at a lower Holm-significant count:**
85/180 Holm-significant (was 119/180), 128/180 BH-significant (was 132/180). Every Holm-significant
cell in the new run was already Holm-significant in the stale run (0 gained, 34 lost) — the stale
run overstated spread, never understated it. PFC and TEO drop to 0/20 Holm-significant (were 7/20,
13/20) but this is a Holm-family-reranking effect, not a vanished effect: their raw p-values and
effect sizes are essentially unchanged, and both **do** survive BH/FDR (PFC 7/20, TEO 14/20).
MST/V4/V1/V2 are essentially unchanged; MT and V3a/d drop moderately (20/20→14/20, 13/20→8/20).

**Q2 (does omission type matter, omissions only) is still fully null**: 1/180 Holm/BH-significant
(was 0/180) — one nominal cell in a 180-cell family is exactly what a true null predicts.

Convergence-warning cells rose from 42/40 (stale run, Q1/Q2) to 88/68 (this run) — not yet
root-caused; flagged as open in the new lab node rather than investigated further.

Full comparison and receipts: `artifacts/.lab/fig04-glmm-all-areas-timeresolved-v2-20260814.json`
(supersedes `fig04-glmm-all-areas-timeresolved-20260813`, which is marked `superseded`, not deleted).

### RESOLVED 2026-08-14 — the v2 rerun above still had no trial-level artifact rejection

User follow-up: "we gotta make sure we are excluding intervals with artifacts ; artifacts are
sharp increase in power that across trials in the same condition are not present." The v2
extraction fixed the stale-corpus bug but applied **zero** artifact rejection — a single trial
with a sharp, condition-atypical power spike was averaged into the session mean unmodified.

`jnwb/artifact_repair.py` already had the right tool for this (built 2026-08-13, but only ever
used by `context/figures/fig_v1_omission_band_dynamics/band_power_dynamics.py`, never by any TFR
condition-map extraction): `repair_band_artifacts` — per band, per-(trial,time) one-sided robust-z
against the cross-trial median (`z_thresh=6.0`), flagged cells replaced by the cross-trial median
(substitution, trial kept). Promoted it into `jnwb/artifact_repair.py` as the canonical home,
added a synthetic self-test, and validated the flagged-fraction rate (2–11%/band) against this
project's own prior use of the identical function before trusting it on the full corpus.

`scripts/extract_condition_tfr_maps_v3.py` (copy of v2, adds this repair before the dB pipeline) →
`outputs/condition_tfr_maps_p1d1p2d2p3_v3/maps.npz` (485/485 files, 479 with ≥1 flagged cell).
`fig04_glmm_all_areas_timeresolved_v3.py` reran the GLMM on it:

**Q1** recovers most of what v2 (no repair) had lost: **109/180 Holm-significant** (v1 stale=119,
v2 no-repair=85), 133/180 BH-significant. Every v2-significant cell stayed significant (0 lost),
24 more gained. MT fully recovers (14/20→20/20); V1/V2 improve **past** the stale run (12/20→15/20
each vs stale's 13/20); PFC/TEO partially recover (0/20→5/20, 0/20→4/20) but stay below the stale
run's 7/20, 13/20 — not yet explained, flagged open. **Q2 returns to a clean 0/180** (matches the
original stale-run null exactly; v2's stray 1/180 is gone).

Full comparison: `artifacts/.lab/fig04-glmm-all-areas-timeresolved-v3-20260814.json` (supersedes
the v2 node above, which stays `superseded`, not deleted). **This v3 result is current best
estimate** — use 109/180, not v1's 119/180 or v2's 85/180.

### RESOLVED 2026-08-15 — classify_omission_units_jitter.py / _condition.py results depended on corpus size and session order, not just session content

Both scripts shared a single `np.random.default_rng(42)` across their whole sorted-session loop,
consumed sequentially per unit inside `analyse_session`. Adding the 22nd session
(`sub-V198o_ses-230629`, sorts before the 4 pre-existing V198o sessions) silently shifted the RNG
draw stream for every session processed after that point — the raw-value discrepancy for
unchanged sessions flagged as unresolved in
`artifacts/.lab/bh-fdr-backwards-divisor-fix-20260814.json`. Fixed: each session now seeds its own
RNG from `(BASE_SEED, zlib.crc32(filename))` — deterministic, and independent of corpus
membership/order/size by construction, not just by convention.

With the RNG now fixed, the BH-formula-only delta (the original Phase 0 fix) could finally be
isolated cleanly by recomputing q-values from the current, deterministic 22-session run's own raw
p-values under the old buggy divisor and diffing against the corrected classification:
`classify_omission_units_condition.py`, ALPHA=0.025 — buggy BH would call **215 more** units O+
and **366 more** O- than the fix allows (correct: O+ 133, O- 454; buggy-on-same-data: O+ 348,
O- 820) — the bug was purely liberal (under-corrected, inflated significance counts), consistent
with dividing by a smaller/backwards denominator. **Current O+ 133 / O- 454 (ALPHA=0.025) is the
correct, trustworthy number for this script.**

### ⚠ NEW, HIGH-SEVERITY, UNRESOLVED — classify_omission_units_jitter.py cannot detect anything under the now-correct BH code

The full-corpus rerun (RNG fix applied, already-correct BH) classifies **all 9,056 units as `ns`
— zero O+, O-, or O++ anywhere.** Not a bug in this rerun: `p_rate`/`p_ramp` are permutation
p-values with a hard floor (`(1 + count) / (N_SHUFFLES + 1)` = 1/1001 = 0.000999 at
`N_SHUFFLES=1000`), only 13/9,056 units ever reach that floor, and at n=9,056 with `ALPHA=0.01`
BH's rank-1 threshold (~1.1e-6) is roughly 900× smaller than the floor this test can ever
produce — 13 units is not enough of a tied block for BH's step-up procedure to let any survive.
Contrast: `classify_omission_units_condition.py` uses the identical floor and shuffle count but
587/9,056 units hit the floor (a much larger, more prevalent effect), so its tied block survives
collectively — that is why one script still returns real counts and the other returns none.

**This means every historical O+/O-/O++ number this specific script has ever produced — not just
today's rerun — should be treated as unusable under the corrected BH code**, until the test's
resolution (`N_SHUFFLES`) or correction scope (currently one BH family across all 10 areas ×
9,056 units) is revisited. The old buggy, over-liberal BH was silently masking this. How to fix
it (more shuffles, a narrower per-area correction family, a different alpha, or accepting this
design is underpowered at unit-level granularity on this corpus) is a real scientific choice with
real compute-cost tradeoffs, **not decided in this session** — flagged for Hamm.

Full comparison and both findings: `artifacts/.lab/rng-determinism-and-bh-isolation-20260815.json`.

### Superseded paths — do not restore

These appear in pre-2026-08-12 documents and **do not exist**:
`D:/analysis/nwb/` · `D:/workspace/data/tfr_arrays/` · `D:/workspace/data/metadata/`.
Earlier corpus statements of "21 NWB sessions" and "1,236 TFR files" describe pre-migration
inventories. `sub-V198o_ses-230629_rec` was added to both inventories by explicit decision on
2026-08-11, which is the 21→22 change.

## 2. Paradigm

A trial is `fx – p1 – d1 – p2 – d2 – p3 – d3 – p4 – d4`. Slots p1–p4 carry stimulus identity;
`fx` and d1–d4 are a gray screen with fixation dot. **Delays and the fixation interval are
visually identical to an omission**, so an omission produces three consecutive identical empty
periods: the omitted slot, flanked by two delays that serve as a within-trial control matched
in everything but expectation.

Twelve conditions: `AAAB AXAB AAXB AAAX BBBA BXBA BBXA BBBX RRRR RXRR RRXR RRRX`. Nine contain
an omission; minimum omitted slot is 2, so a pre-omission delay always exists.

Ten analysis areas: V1, V2, V3, V4, MT, MST, TEO, FST, FEF, PFC. Eleven-to-twelve *labels*
appear in filenames (V3, V3a, V3d separately); ten *analysis regions* is the correct count.

## 3. Superseded claims — do not restore

The 2026-07-27 handout listed these as "protected invariants". They are presentation-layer
constants that no script computes from data.
`scripts/archive_oneoff/compute_empirical_census_and_power.py` holds them as hardcoded dict
literals and writes `artifacts/data/empirical_response_census.json`, consumed by nine
downstream scripts. Receipt: `artifacts/.lab/census_provenance_synthetic_finding_20260728.json`.

| Retracted | Status |
|---|---|
| Primary census 8,597 units; O+ = 421/8,597 = 4.90% | **Synthetic.** Real unit table has 6,655 units. Two-subject screening gave ~20 O+ of ~5,000 (~0.4%). |
| LFP census 8,736 channels; beta modulation 6,771/8,736 = 77.51% | **Synthetic.** Real per-channel census is 9,344 channels. |
| GLMM OR = 3.08, CI [2.51, 3.78], z = 10.726, p = 7.25e-27 | **Never fitted.** |
| Figure 8 alpha 5,816/8,736 = 66.58% | **Synthetic denominator.** |
| "Omission broadly perturbs low-frequency cortical state" | **Directional claim, not supported.** Magnitude holds; direction does not. |
| "Sustained beta elevation during omission" | **Not reproduced** at any level. |

32 of 40 displayed cells in the LFP table were exact whole percentages — probability ≈3×10⁻²⁵
for measured proportions at those denominators.

## 4. Current findings, with receipts

From `outputs/lfp_band_census_v2/` (`receipt.json`, `glmm_results.json`, `glmm_summary.csv`).
Census receipt 2026-07-29: 1,236 TFR files scanned, 909 omission-condition files processed,
18 skipped, 420,480 rows, 23 sessions, median 39 trials/channel.

**Low-frequency power is modulated everywhere.** Mean absolute change in the omitted slot vs
each channel's own baseline: theta 1.06 dB, alpha 1.02, beta 0.79, low gamma 0.55, high gamma
0.42. Low-frequency modulation ≈ 2× gamma.

**The direction is not shared.** Pooled 23-session model (84,096 obs, random intercept per
session; Intercept tests common sign): theta p_BH 0.42, alpha 0.59, beta 0.29, low gamma 1.00,
high gamma 0.94 — null in every band. This tests common *sign*, not presence of modulation.

**Animals disagree in sign.** C31o (8 sessions) fell in every band below 50 Hz (theta −1.58 dB,
q 5.0e−5; alpha −1.36, q 1.0e−4; beta −0.89, q 4.3e−3; low gamma −0.39, q 2.0e−3). V182o (10)
rose in all five. V198o (5) reached significance in no band. The split survives holding area
constant in 7 of 8 testable area×band comparisons.

**V3a/d vs V1 elevation, animal-controlled (corrected 2026-08-05).** Model F — area effects
with subject as an explicit additive fixed effect, session-level, 23 sessions, 3 subjects:
**beta +1.11 dB, p 0.0056, q_BH 0.0147**; **low gamma +0.34 dB, q_BH 0.0147**. Alpha (+0.75,
q 0.129), theta and high gamma do not survive. Two prior bugs fixed: the area-pooling dict
omitted the raw `"V3"` label, and a local BH function inverted rank order.
Receipt: `artifacts/.lab/v3ad_beta_glmm_two_bugs_fixed_20260805.json`.

**Spiking onset-latency hierarchy (H1 feedforward / H2 feedback / H3 superposition), 2026-08-15.**
`scripts/fit_class_onset_latency.py` fits a causality-bounded exponential onset to the
population PSTH of each response class (omnibus, S+, S-, O+, O-) per area, per session. First
run was dominated by a boundary-pinning artifact (t0 forced to ~0ms by a causal-smoothing
warmup bug plus a baseline window that overlapped a genuine pre-stimulus ramp) — up to 85.5% of
gate-passing omnibus cells and 34.9% of S+ cells were artifact, not real onsets. **Root-cause
fixed** (150ms real smoothing-warmup margin; S/omnibus baseline moved to -400..-150ms using the
fx=-500ms fixation marker; O+/O- deliberately left alone since their pre-onset period is the
anticipatory-omission-expectation signal the classes exist to measure, not noise). Post-fix,
pinning drops to 12.0% overall (S+ 4.8%, omnibus 10.3%; O+/O-/S- now 0 gate-passing cells —
genuinely underpowered, not artifact-inflated). Current best estimate: **omnibus** 7 areas,
rho=0.36, p_holm=0.44 (not significant); **S+** 8 areas, rho=0.62, p_holm=0.22 (not significant,
but a real, substantially strengthened signal — every area's onset is now above the 40ms visual-
latency floor, versus 3/8 areas violating it pre-fix). **O+/O-/S-**: insufficient data for any
per-area comparison, independent of the fix — a session/unit-count ceiling. Layer-stratified
rerun (`scripts/fit_class_onset_latency_by_layer.py`) confirms the same ceiling one level down:
only 7 of 15 area×class cells get any layer breakdown at all, one of those (FEF-sup-omnibus) is
still boundary-pinned despite the fix, and no area has enough sessions across all three layers to
support a laminar-onset claim except PFC (sup/mid/deep all present, n=3-4 sessions each,
suggestive sup→mid→deep ordering, CIs too wide to trust).
Receipts: `artifacts/.lab/onset-hierarchy-h1h2h3-fixed-20260815.json`,
`artifacts/.lab/onset-hierarchy-layer-stratified-20260815.json`.

## 5. Structural facts that constrain inference

- **Area and subject are confounded corpus-wide.** No area was recorded in all three animals.
  The area×subject graph is nevertheless connected (every area in ≥2 subjects), so additive
  effects are jointly identifiable.
- **The area partition is an assumption.** 27 of 51 probes span multiple areas; in 26 the
  boundary is channel 64 of 128, and the one three-area probe splits at 42 and 85 — uniform
  divisions in listing order. Labels are disjoint (which removes aliasing) but this does not
  establish that a channel lies in the area its label names. **V3a and V3d pool to V3.**
- **Putative layer** comes from the vFLIP2 alpha/beta-to-gamma crossover and returns `na` for
  roughly two thirds of channels. Coverage is also imbalanced by animal
  (Kruskal-Wallis H = 12.80, P = 0.0017) and ~3× by area. A laminar model fitted only where the
  crossover converged reports a property of the estimator, not of cortex.
- **All 6,655 screened units carry `layer = Superficial`** in the classification table. Any
  laminar statement drawn from that field describes a default.
- **The unit classifier is one-sided.** 3,457 of 6,655 units have a negative omission effect;
  none reaches p = 0.05.
- **Four passes report four different O+ counts** (386, 19, 7, and a retracted 421). Confirm
  which script and criteria produced any figure before quoting it.

## 6. Blocked and gated

| Item | Status |
|---|---|
| **Figure 3 — unit census** | O+ prevalence on three subjects is the headline number still owed. Synthetic lineage must not be reused. |
| **Figure 4 — identity decoding** | `_v2` tables exist but the random-CV result is confounded; the cycle-deconfounded estimate is ≈ chance. **Do not promote the 0.601 accuracy.** Requires: p4 label-fix rerun with provenance, grouped/cycle-safe CV, corpus-scale permutation null, no hardcoded values in panels, a stats receipt per panel, and headline wording determined from the deconfounded result even if null. |
| **Figure 5** | Preserve the distinction between descriptive channel-level effects and session-level Model F. |
| **Figure 6** | Empirical ratio-based products, current bands, area segmentation verified before averaging. A heatmap is descriptive without a session-level window/band receipt. |
| **Figure 7** | Establish the statistic and its sampling unit before interpreting coupling as routing. Matched-count resampling if spike counts differ between conditions. |
| **All TFR figures** | `tfr_ok` gate fixed 2026-08-14 (was a stale scan pattern, not a data problem — see §1). `suite_tfr_ready` still 0/22 pending the separate, unresolved `sidecar_ok`/`meta_dir` gap (§1); gate on `tfr_ok` + explicit condition/quality checks instead until that's resolved. |
| **Laminar sign question** | Blocked on vFLIP coverage. |

### RESOLVED 2026-08-16 — the cycle-deconfounded Figure 4 estimate was computed on a unit-identity bug; conclusion unchanged after the fix

`jnwb.omission_identity.decode_identity_cycle_deconfound` (the function
`compute_omission_identity_cycle_deconfound_v3.py` calls to produce the "≈ chance" estimate
above) and three sibling functions in the same module built `unit_ids =
units_df["unit_id"].tolist()` — the per-probe-local kilosort column, which can have gaps
relative to row position — and passed those values into `session.get_spike_times()`, whose
primary lookup is by row position. A column value equal to another row's position silently
returns that OTHER unit's real spike train — the exact collision already caught and fixed in
`jnwb/trajectory.py` (`sub-C31o_ses-230816_rec`, PFC row 3 vs. `unit_id` column 4.0, 3,470 vs.
449 real spikes) but never propagated to `omission_identity.py`. `jnwb/unit_classification.py`
and `jnwb/structured_identity_m2a.py` (the approved Milestone 2A path) were already correct.

Fixed all 4 call sites to use row position. Full-corpus rerun (22 sessions × 7 areas, 60/154
cells succeed, `n_permutations=200`, `seed=42`): mean LOCO accuracy (mean-centered) = **0.4960**,
6/60 cells nominally significant at p<0.05 — materially unchanged from the pre-fix ~0.495 cited
in `artifacts/.lab/agent-harness-audit-20260810.json`. **The "do not promote 0.601, treat as
chance" conclusion above still holds** — it is now verified on a corrected identity basis
rather than a coincidentally-similar buggy one. Receipt:
`artifacts/.lab/bug-omission-identity-unit-id-column-vs-row-position-20260816.json`. A true
pre-fix full-corpus CSV was not preserved (overwritten by an interim sanity-check run before it
could be copied aside) — the ~0.495 comparison figure is the prior agent's own written number,
not a byte-level diff; flagged as a provenance gap in the receipt, not hidden.

## 7. Open questions

1. O+ prevalence on three subjects.
2. Two-window estimates per band × area × layer.
3. Does laminar sampling explain the sign inconsistency?
4. Methods gaps absent from every source: surgery/implant, full stimulus specification,
   fixation and reward schedule, spike-sorting parameters and quality tiers, CSD computation.
5. Author list; three reference defects (Wacongne 2011 journal/DOI, Bastos 2015 DOI suffix,
   Rao & Ballard 1999 cited for a Bastos 2012 laminar claim).
6. Graph health — **re-derive, do not inherit.** The last recorded audit (330 nodes, ~87 with
   receipts against ~276 `confirmed`, 40 edges to a nonexistent `mission` node) is stale; the
   graph now holds 395 JSON nodes.

## 8. Manuscript lineage

Markdown drafts are the live line and carry no number from the DOCX. `context/drafts/
omission-a-draft-v3.md` is current. The DOCX lineage carries the §3 synthetic numbers and is
retained for history; `omission-2026-manuscript-master.docx` is the original and is not
overwritten. A Word lock file has been observed on the master — check before any write.

## 9. Model choice for omission-a

Not fixed by doctrine. The design supports session as a grouping factor; three subjects cannot
identify a subject random-effect variance, so subject enters by stratification or as an explicit
fixed term. Whether the paper reports a mixed model is a project decision recorded here, and it
is currently **unsettled**: earlier material named a GLMM backbone while other material deferred
GLMM to a later paper.
